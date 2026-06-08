"""Explicit native FTDI D3XX DLL surface for fast-path streaming."""

import ctypes
from dataclasses import dataclass
from typing import ClassVar, Protocol, cast

from py3dscapture.errors import CaptureError
from py3dscapture.transport.d3xx_backend import D3xxBackendError

FT_OK = 0
FT_TIMEOUT = 19
FT_IO_PENDING = 24
FT_IO_INCOMPLETE = 25

FT_STATUS = ctypes.c_uint32
FT_HANDLE = ctypes.c_void_p
UCHAR = ctypes.c_ubyte
ULONG = ctypes.c_uint32
BOOL = ctypes.c_int32
DWORD = ctypes.c_uint32
HANDLE = ctypes.c_void_p
PULONG = ctypes.POINTER(ULONG)


class D3xxNativeHandleProvider(Protocol):
    """Surface used to adapt an opened D3XX handle to the native API layer."""

    def pyd3xx_native_dll(self) -> object | None:
        """Return the loaded PyD3XX DLL object when available."""
        ...

    def pyd3xx_native_handle(self) -> object:
        """Return the native FT_HANDLE-compatible object."""
        ...


class NativeFunction(Protocol):
    """ctypes function surface used by the native API wrapper."""

    argtypes: list[object]
    restype: object

    def __call__(self, *args: object) -> int:
        """Call the native function."""
        ...


class D3xxNativeApiUnavailable(CaptureError):  # noqa: N818
    """Raised when the required native D3XX DLL surface is unavailable."""

    @classmethod
    def missing_dll(cls) -> "D3xxNativeApiUnavailable":
        """Create an error for a missing native DLL provider."""
        return cls("D3XX native DLL surface is unavailable")

    @classmethod
    def missing_function(cls, name: str) -> "D3xxNativeApiUnavailable":
        """Create an error for a missing native DLL function."""
        return cls(f"{name} is unavailable")

    @classmethod
    def null_handle(cls) -> "D3xxNativeApiUnavailable":
        """Create an error for a null native handle."""
        return cls("native D3XX handle is null")

    @classmethod
    def missing_handle(cls) -> "D3xxNativeApiUnavailable":
        """Create an error for a missing native handle provider."""
        return cls("native D3XX handle is unavailable")


class _NativeOffsetPair(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, object]]] = [
        ("Offset", DWORD),
        ("OffsetHigh", DWORD),
    ]


class _NativeOffsetUnion(ctypes.Union):
    _fields_: ClassVar[list[tuple[str, object]]] = [
        ("offset_pair", _NativeOffsetPair),
        ("Pointer", ctypes.c_void_p),
    ]


class NativeOverlapped(ctypes.Structure):
    """Windows OVERLAPPED layout used by FTD3XX asynchronous pipe APIs."""

    _fields_: ClassVar[list[tuple[str, object]]] = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("u", _NativeOffsetUnion),
        ("hEvent", HANDLE),
    ]


@dataclass(frozen=True, slots=True)
class NativeTransferResult:
    """D3XX native transfer status and byte count."""

    status: int
    transferred: int


class D3xxNativeApi:
    """Typed native D3XX DLL function surface.

    This class owns the direct DLL calling convention. It may be constructed
    from a PyD3XX-backed handle, but callers use this explicit API instead of
    reaching into PyD3XX private module attributes.
    """

    def __init__(self, dll: object, handle: object) -> None:
        """Create a native API wrapper over one open FT_HANDLE.

        Args:
            dll: Loaded D3XX DLL object, normally a ``ctypes.WinDLL``.
            handle: FT_HANDLE-compatible value from the opened device.

        Raises:
            D3xxNativeApiUnavailable: Required functions or handle are missing.
        """
        self._dll = dll
        self._handle = _coerce_handle(handle)
        self._ft_read_pipe_ex = self._bind_function(
            "FT_ReadPipeEx",
            [FT_HANDLE, UCHAR, ctypes.c_void_p, ULONG, PULONG, ctypes.c_void_p],
        )
        self._ft_get_overlapped_result = self._bind_function(
            "FT_GetOverlappedResult",
            [FT_HANDLE, ctypes.c_void_p, PULONG, BOOL],
        )
        self._ft_initialize_overlapped = self._bind_function(
            "FT_InitializeOverlapped",
            [FT_HANDLE, ctypes.c_void_p],
        )
        self._ft_release_overlapped = self._bind_function(
            "FT_ReleaseOverlapped",
            [FT_HANDLE, ctypes.c_void_p],
        )
        self._ft_abort_pipe = self._bind_function(
            "FT_AbortPipe",
            [FT_HANDLE, UCHAR],
        )
        self._ft_set_stream_pipe = self._bind_function(
            "FT_SetStreamPipe",
            [FT_HANDLE, BOOL, BOOL, UCHAR, ULONG],
        )

    @classmethod
    def from_pyd3xx_handle(cls, provider: D3xxNativeHandleProvider) -> "D3xxNativeApi":
        """Create a native API wrapper from an opened PyD3XX-backed handle.

        Args:
            provider: Opened handle exposing the limited native provider
                surface.

        Returns:
            Native API wrapper for the same open D3XX handle.

        Raises:
            D3xxNativeApiUnavailable: PyD3XX does not expose the required DLL
                or handle.
        """
        dll = provider.pyd3xx_native_dll()
        if dll is None:
            raise D3xxNativeApiUnavailable.missing_dll()
        try:
            handle = provider.pyd3xx_native_handle()
        except D3xxBackendError as exc:
            raise D3xxNativeApiUnavailable(str(exc)) from exc
        return cls(dll, handle)

    def initialize_overlapped(self, overlapped: NativeOverlapped) -> None:
        """Initialize one OVERLAPPED object for asynchronous D3XX I/O."""
        status = self._ft_initialize_overlapped(self._handle, _overlapped_ptr(overlapped))
        _check_native_status("FT_InitializeOverlapped", status)

    def release_overlapped(self, overlapped: NativeOverlapped) -> None:
        """Release one initialized OVERLAPPED object."""
        status = self._ft_release_overlapped(self._handle, _overlapped_ptr(overlapped))
        _check_native_status("FT_ReleaseOverlapped", status)

    def set_stream_pipe(self, pipe: int, stream_size: int) -> None:
        """Configure fixed-size streaming on one read pipe."""
        status = self._ft_set_stream_pipe(
            self._handle,
            BOOL(False),
            BOOL(False),
            UCHAR(pipe),
            ULONG(stream_size),
        )
        _check_native_status("FT_SetStreamPipe", status)

    def abort_pipe(self, pipe: int) -> None:
        """Abort pending transfers for one pipe."""
        status = self._ft_abort_pipe(self._handle, UCHAR(pipe))
        _check_native_status("FT_AbortPipe", status)

    def read_pipe_ex(
        self,
        pipe: int,
        buffer: ctypes.Array[ctypes.c_char],
        length: int,
        overlapped: NativeOverlapped,
    ) -> NativeTransferResult:
        """Submit or complete one native ``FT_ReadPipeEx`` call."""
        if length > ctypes.sizeof(buffer):
            raise ValueError
        transferred = ULONG(0)
        status = self._ft_read_pipe_ex(
            self._handle,
            UCHAR(pipe),
            ctypes.cast(buffer, ctypes.c_void_p),
            ULONG(length),
            ctypes.byref(transferred),
            _overlapped_ptr(overlapped),
        )
        return NativeTransferResult(status=int(status), transferred=int(transferred.value))

    def get_overlapped_result(
        self,
        overlapped: NativeOverlapped,
        *,
        wait: bool,
    ) -> NativeTransferResult:
        """Return completion status for one pending overlapped operation."""
        transferred = ULONG(0)
        status = self._ft_get_overlapped_result(
            self._handle,
            _overlapped_ptr(overlapped),
            ctypes.byref(transferred),
            BOOL(wait),
        )
        return NativeTransferResult(status=int(status), transferred=int(transferred.value))

    def _bind_function(self, name: str, argtypes: list[object]) -> NativeFunction:
        function = getattr(self._dll, name, None)
        if function is None:
            raise D3xxNativeApiUnavailable.missing_function(name)
        function = cast("NativeFunction", function)
        function.argtypes = argtypes
        function.restype = FT_STATUS
        return function


def _coerce_handle(handle: object) -> ctypes.c_void_p:
    if isinstance(handle, ctypes.c_void_p):
        if handle.value is None:
            raise D3xxNativeApiUnavailable.null_handle()
        return handle
    if isinstance(handle, int):
        if handle == 0:
            raise D3xxNativeApiUnavailable.null_handle()
        return ctypes.c_void_p(handle)
    value = getattr(handle, "value", None)
    if isinstance(value, int) and value != 0:
        return ctypes.c_void_p(value)
    raise D3xxNativeApiUnavailable.missing_handle()


def _overlapped_ptr(overlapped: NativeOverlapped) -> ctypes.c_void_p:
    return ctypes.cast(ctypes.byref(overlapped), ctypes.c_void_p)


def _check_native_status(function: str, status: int) -> None:
    if status != FT_OK:
        raise D3xxBackendError(function, status)
