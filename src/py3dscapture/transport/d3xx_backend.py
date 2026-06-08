# ruff: noqa: N802
"""Optional FTDI D3XX backend boundary."""

import ctypes
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import import_module
from types import ModuleType
from typing import Any, Literal, Protocol, cast

from py3dscapture.devices.n3dsxl_ftd3 import DeviceCandidate, classify_n3dsxl_device
from py3dscapture.errors import CaptureError, OptionalDependencyError
from py3dscapture.protocol.sizes import N3DSXL_VENDOR_ID
from py3dscapture.transport.libusb_backend import UsbDeviceInfo

FT_OK = 0
D3XX_OPEN_BY_SERIAL_NUMBER = 0x01
D3XX_OPEN_BY_INDEX = 0x10
D3XX_DEFAULT_TIMEOUT_MS = 500
PYD3XX_MODULE_NAMES = ("PyD3XX", "pyd3xx")


class D3xxBinding(Protocol):
    """Subset of the PyD3XX module needed for device enumeration and I/O.

    The real package exposes module-level functions and factory classes. This
    protocol describes only the calls used by ``D3xxBackend`` and ``D3xxHandle``.
    """

    FT_Pipe: Any
    FT_Buffer: Any

    def FT_CreateDeviceInfoList(self) -> tuple[int, int]:
        """Return D3XX status and number of devices.

        Returns:
            ``(status, count)`` where status must be ``FT_OK``.
        """
        ...

    def FT_GetDeviceInfoDetail(self, index: int) -> tuple[int, object]:
        """Return D3XX status and one device information node.

        Args:
            index: Zero-based device index in the current D3XX device list.

        Returns:
            ``(status, detail)`` where detail contains ID, description,
            serial-number, and flag fields.
        """
        ...

    def FT_Create(self, identifier: object, open_flag: int, device: object) -> int:
        """Open a D3XX device into an initialized FT_Device object.

        Args:
            identifier: Serial number or index used by the selected open flag.
            open_flag: D3XX open mode such as serial-number or index.
            device: Device detail object to initialize.

        Returns:
            D3XX status code.
        """
        ...

    def FT_Close(self, device: object) -> int:
        """Close an opened D3XX device object.

        Args:
            device: Open D3XX device object.

        Returns:
            D3XX status code.
        """
        ...

    def FT_AbortPipe(self, device: object, pipe: object) -> int:
        """Abort one D3XX native pipe.

        Args:
            device: Open D3XX device object.
            pipe: D3XX pipe object with the selected pipe ID.

        Returns:
            D3XX status code.
        """
        ...

    def FT_SetStreamPipe(
        self,
        device: object,
        all_write_pipes: bool,
        all_read_pipes: bool,
        pipe: object,
        stream_size: int,
    ) -> int:
        """Configure streaming for one D3XX native pipe.

        Args:
            device: Open D3XX device object.
            all_write_pipes: Whether all write pipes should be affected.
            all_read_pipes: Whether all read pipes should be affected.
            pipe: D3XX pipe object with the selected pipe ID.
            stream_size: Stream transfer size in bytes.

        Returns:
            D3XX status code.
        """
        ...

    def FT_ReadPipe(
        self,
        device: object,
        pipe: object,
        buffer_length: int,
        overlapped_timeout_ms: int,
    ) -> tuple[int, object, int]:
        """Read bytes from one D3XX native pipe.

        Args:
            device: Open D3XX device object.
            pipe: D3XX pipe object with the selected pipe ID.
            buffer_length: Maximum read length in bytes.
            overlapped_timeout_ms: Read timeout in milliseconds.

        Returns:
            ``(status, buffer, transferred)``.
        """
        ...

    def FT_ReadPipeEx(
        self,
        device: object,
        pipe: object,
        buffer_length: int,
        overlapped_timeout_ms: int,
    ) -> tuple[int, object, int]:
        """Read bytes from one D3XX native stream pipe.

        Args:
            device: Open D3XX device object.
            pipe: D3XX pipe object with the selected pipe ID.
            buffer_length: Maximum read length in bytes.
            overlapped_timeout_ms: Read timeout in milliseconds.

        Returns:
            ``(status, buffer, transferred)``.
        """
        ...

    def FT_WritePipe(
        self,
        device: object,
        pipe: object,
        buffer: object,
        buffer_length: int,
        overlapped_timeout_ms: int,
    ) -> tuple[int, int]:
        """Write bytes to one D3XX native pipe.

        Args:
            device: Open D3XX device object.
            pipe: D3XX pipe object with the selected pipe ID.
            buffer: D3XX buffer object containing payload bytes.
            buffer_length: Number of bytes to write.
            overlapped_timeout_ms: Write timeout in milliseconds.

        Returns:
            ``(status, transferred)``.
        """
        ...


class D3xxBackendError(CaptureError):
    """Raised when a D3XX API call fails or returns unsupported data.

    Attributes:
        function: D3XX function or parser step associated with the failure.
        status: Optional native status code.
        field_name: Optional detail field that was missing or invalid.
    """

    def __init__(
        self,
        function: str,
        status: int | None = None,
        *,
        field_name: str | None = None,
    ) -> None:
        """Create a structured D3XX backend failure.

        Args:
            function: D3XX function or parser step associated with the failure.
            status: Optional native status code.
            field_name: Optional detail field that was missing or invalid.
        """
        message = _d3xx_error_message(function, status, field_name)
        super().__init__(message)
        self.function = function
        self.status = status
        self.field_name = field_name

    @classmethod
    def missing_field(cls, field_name: str) -> "D3xxBackendError":
        """Create an error for an unsupported D3XX detail shape.

        Args:
            field_name: Required field that was not present.

        Returns:
            Structured backend error.
        """
        return cls("missing field", field_name=field_name)

    @classmethod
    def invalid_integer(cls, field_name: str) -> "D3xxBackendError":
        """Create an error for an integer field that cannot be parsed.

        Args:
            field_name: Integer field that could not be converted.

        Returns:
            Structured backend error.
        """
        return cls("invalid integer", field_name=field_name)

    @classmethod
    def invalid_candidate(cls) -> "D3xxBackendError":
        """Create an error for an unsupported D3XX candidate object.

        Returns:
            Structured backend error for a wrong candidate type.
        """
        return cls("invalid candidate")


@dataclass(frozen=True, slots=True)
class D3xxDeviceInfo:
    """D3XX listing information normalized for N3DSXL classification.

    Attributes:
        index: Zero-based D3XX device index.
        usb_info: USB identity reconstructed from D3XX detail fields.
        flags: Optional D3XX flags field.
        device_id: Raw D3XX device ID containing VID/PID information.
    """

    index: int
    usb_info: UsbDeviceInfo
    flags: int | None
    device_id: int


@dataclass(frozen=True, slots=True)
class D3xxDeviceCandidate:
    """N3DSXL candidate found through the D3XX driver backend.

    Attributes:
        candidate: Accepted N3DSXL candidate after USB identity classification.
        index: Zero-based D3XX device index.
        flags: Optional D3XX flags field.
        device_id: Raw D3XX device ID containing VID/PID information.
        backend_kind: Normalized backend label for metadata.
    """

    candidate: DeviceCandidate
    index: int
    flags: int | None
    device_id: int
    backend_kind: str = "d3xx"


class D3xxHandle:
    """Opened D3XX handle with idempotent close.

    The handle implements the pipe operations expected by ``N3DSXLProtocol`` and
    records which pipes were configured for stream reads.
    """

    backend_kind: Literal["d3xx"] = "d3xx"

    def __init__(
        self,
        binding: D3xxBinding,
        device: object,
        candidate: DeviceCandidate,
        d3xx_candidate: D3xxDeviceCandidate | None = None,
    ) -> None:
        """Create a handle from an opened PyD3XX device detail object.

        Args:
            binding: PyD3XX-compatible module binding.
            device: Open D3XX device detail object.
            candidate: Accepted N3DSXL candidate for metadata.
            d3xx_candidate: Original D3XX candidate, required for reconnect.
        """
        self._binding = binding
        self._device = device
        self.candidate = candidate
        self._d3xx_candidate = d3xx_candidate
        self._closed = False
        self._stream_pipes: set[int] = set()

    def close(self) -> None:
        """Close the D3XX device handle.

        The method is idempotent after the first successful or attempted close.

        Raises:
            D3xxBackendError: ``FT_Close`` returns a non-OK status.
        """
        if self._closed:
            return
        try:
            _check_status("FT_Close", self._binding.FT_Close(self._device))
        finally:
            self._closed = True

    def abort_pipe(self, pipe: int) -> None:
        """Abort one D3XX native pipe.

        Args:
            pipe: D3XX pipe ID.

        Raises:
            D3xxBackendError: ``FT_AbortPipe`` fails.
        """
        pipe_object = _pipe_from_id(self._binding, pipe)
        _check_status("FT_AbortPipe", self._binding.FT_AbortPipe(self._device, pipe_object))

    def create_pipe(self) -> None:
        """Keep protocol compatibility with the shared FTD3 transport surface.

        The D3XX native API does not need the libusb command-pipe create
        payload, so this operation is intentionally a no-op.
        """

    def reconnect_after_drain(self) -> None:
        """Close and reopen after the initial drain, matching cc3dsfs' D3XX path.

        Raises:
            D3xxBackendError: The handle lacks original candidate metadata, or
                the D3XX detail lookup/open call fails.
        """
        if self._d3xx_candidate is None:
            raise D3xxBackendError.invalid_candidate()
        self.close()
        _, detail = _status_and_value(
            "FT_GetDeviceInfoDetail",
            self._binding.FT_GetDeviceInfoDetail(self._d3xx_candidate.index),
        )
        _check_status(
            "FT_Create",
            self._binding.FT_Create(
                _open_identifier(self._d3xx_candidate),
                _open_flag(self._d3xx_candidate),
                detail,
            ),
        )
        self._device = detail
        self._closed = False

    def set_stream_pipe(self, pipe: int, length: int) -> None:
        """Configure one D3XX native stream pipe.

        Args:
            pipe: D3XX pipe ID to configure.
            length: Stream transfer length in bytes.

        Raises:
            D3xxBackendError: ``FT_SetStreamPipe`` fails.
        """
        pipe_object = _pipe_from_id(self._binding, pipe)
        _check_status(
            "FT_SetStreamPipe",
            self._binding.FT_SetStreamPipe(
                self._device,
                False,
                False,
                pipe_object,
                length,
            ),
        )
        self._stream_pipes.add(pipe)

    def read_pipe(
        self,
        pipe: int,
        length: int,
        timeout_ms: int = D3XX_DEFAULT_TIMEOUT_MS,
    ) -> bytes:
        """Read bytes from one D3XX native pipe.

        Args:
            pipe: D3XX pipe ID to read.
            length: Maximum number of bytes to read.
            timeout_ms: Read timeout in milliseconds.

        Returns:
            Bytes read from the native D3XX pipe.

        Raises:
            D3xxBackendError: The D3XX read call fails or returns unsupported
                buffer metadata.
        """
        if pipe in self._stream_pipes:
            return self._read_stream_pipe(pipe, length, timeout_ms)
        direct = _direct_read_pipe(self._binding, self._device, pipe, length, timeout_ms)
        if direct is not None:
            return direct
        pipe_object = _pipe_from_id(self._binding, pipe)
        result = self._binding.FT_ReadPipe(self._device, pipe_object, length, timeout_ms)
        status, buffer, transferred = _status_buffer_and_transferred("FT_ReadPipe", result)
        _check_status("FT_ReadPipe", status)
        return bytes(_buffer_value(buffer)[:transferred])

    def _read_stream_pipe(self, pipe: int, length: int, timeout_ms: int) -> bytes:
        direct = _direct_read_pipe_ex(self._binding, self._device, pipe, length, timeout_ms)
        if direct is not None:
            return direct
        pipe_object = _pipe_from_id(self._binding, pipe)
        result = self._binding.FT_ReadPipeEx(self._device, pipe_object, length, timeout_ms)
        status, buffer, transferred = _status_buffer_and_transferred("FT_ReadPipeEx", result)
        _check_status("FT_ReadPipeEx", status)
        return bytes(_buffer_value(buffer)[:transferred])

    def write_pipe(
        self,
        pipe: int,
        payload: bytes,
        timeout_ms: int = D3XX_DEFAULT_TIMEOUT_MS,
    ) -> int:
        """Write bytes to one D3XX native pipe.

        Args:
            pipe: D3XX pipe ID to write.
            payload: Bytes to transfer.
            timeout_ms: Write timeout in milliseconds.

        Returns:
            Number of bytes transferred.

        Raises:
            D3xxBackendError: The D3XX write call fails.
        """
        direct = _direct_write_pipe(self._binding, self._device, pipe, payload, timeout_ms)
        if direct is not None:
            return direct
        pipe_object = _pipe_from_id(self._binding, pipe)
        buffer = _buffer_from_bytes(self._binding, payload)
        status, transferred = _status_and_transferred(
            "FT_WritePipe",
            self._binding.FT_WritePipe(
                self._device,
                pipe_object,
                buffer,
                len(payload),
                timeout_ms,
            ),
        )
        _check_status("FT_WritePipe", status)
        return transferred


def load_pyd3xx_binding() -> D3xxBinding:
    """Import the optional PyD3XX module.

    Returns:
        Imported module cast to the D3XX binding protocol.

    Raises:
        OptionalDependencyError: Neither supported PyD3XX module name can be
            imported.
    """
    for module_name in PYD3XX_MODULE_NAMES:
        try:
            return cast("D3xxBinding", import_module(module_name))
        except ImportError:
            continue
    raise OptionalDependencyError("PyD3XX", "d3xx")


class D3xxBackend:
    """FTDI D3XX-backed device enumeration.

    This backend is used as a fallback when libusb cannot open an otherwise
    accepted N3DSXL because the installed Windows driver belongs to D3XX.
    """

    def __init__(self, binding: D3xxBinding | None = None) -> None:
        """Create a backend using an injected or optional PyD3XX binding.

        Args:
            binding: Optional test or real PyD3XX binding. When omitted, the
                optional dependency is imported lazily.

        Raises:
            OptionalDependencyError: ``binding`` is omitted and PyD3XX is not
                installed.
        """
        self._binding = binding or load_pyd3xx_binding()

    def iter_devices(self) -> tuple[D3xxDeviceInfo, ...]:
        """Return D3XX devices visible through the binding.

        Returns:
            Tuple of normalized D3XX device information.

        Raises:
            D3xxBackendError: The binding returns a non-OK status or an
                unsupported detail shape.
        """
        _, count = _status_and_value(
            "FT_CreateDeviceInfoList",
            self._binding.FT_CreateDeviceInfoList(),
        )
        devices: list[D3xxDeviceInfo] = []
        for index in range(_int_from_object("FT_CreateDeviceInfoList.count", count)):
            _, detail = _status_and_value(
                "FT_GetDeviceInfoDetail",
                self._binding.FT_GetDeviceInfoDetail(index),
            )
            devices.append(_device_info_from_detail(index=index, detail=detail))
        return tuple(devices)

    def iter_device_candidates(self) -> tuple[D3xxDeviceCandidate, ...]:
        """Return N3DSXL candidates visible through the D3XX backend.

        Returns:
            D3XX devices that pass the same N3DSXL classification policy as the
            libusb path.
        """
        candidates: list[D3xxDeviceCandidate] = []
        for device in self.iter_devices():
            classified = classify_n3dsxl_device(device.usb_info)
            if isinstance(classified, DeviceCandidate):
                candidates.append(
                    D3xxDeviceCandidate(
                        candidate=classified,
                        index=device.index,
                        flags=device.flags,
                        device_id=device.device_id,
                    )
                )
        return tuple(candidates)

    def open(self, candidate: object) -> D3xxHandle:
        """Open one D3XX candidate and return a closeable handle.

        Args:
            candidate: ``D3xxDeviceCandidate`` returned by this backend.

        Returns:
            Open D3XX handle compatible with the N3DSXL protocol pipe surface.

        Raises:
            D3xxBackendError: The candidate type is unsupported, or the D3XX
                detail lookup/open call fails.
        """
        if not isinstance(candidate, D3xxDeviceCandidate):
            raise D3xxBackendError.invalid_candidate()
        _, detail = _status_and_value(
            "FT_GetDeviceInfoDetail",
            self._binding.FT_GetDeviceInfoDetail(candidate.index),
        )
        _check_status(
            "FT_Create",
            self._binding.FT_Create(
                _open_identifier(candidate),
                _open_flag(candidate),
                detail,
            ),
        )
        return D3xxHandle(
            binding=self._binding,
            device=detail,
            candidate=candidate.candidate,
            d3xx_candidate=candidate,
        )


def _device_info_from_detail(*, index: int, detail: object) -> D3xxDeviceInfo:
    device_id = _int_from_object("FT_GetDeviceInfoDetail.ID", _field(detail, "ID"))
    vendor_id, product_id = _vid_pid_from_device_id(device_id)
    usb_info = UsbDeviceInfo(
        bus_number=None,
        address=None,
        vendor_id=vendor_id,
        product_id=product_id,
        product_string=_optional_text(_field(detail, "Description")),
        serial_number=_optional_text(_field(detail, "SerialNumber")),
    )
    flags = _optional_int(_field(detail, "Flags"))
    return D3xxDeviceInfo(index=index, usb_info=usb_info, flags=flags, device_id=device_id)


def _open_identifier(candidate: D3xxDeviceCandidate) -> object:
    serial_number = candidate.candidate.info.serial_number
    if serial_number is not None:
        return serial_number
    return candidate.index


def _open_flag(candidate: D3xxDeviceCandidate) -> int:
    if candidate.candidate.info.serial_number is not None:
        return D3XX_OPEN_BY_SERIAL_NUMBER
    return D3XX_OPEN_BY_INDEX


def _status_and_value(function: str, result: object) -> tuple[int, object]:
    if not isinstance(result, tuple) or len(result) < 2:
        raise D3xxBackendError(function)
    status = _int_from_object(f"{function}.status", result[0])
    if status != FT_OK:
        raise D3xxBackendError(function, status)
    return status, result[1]


def _check_status(function: str, status: object) -> None:
    value = _int_from_object(f"{function}.status", status)
    if value != FT_OK:
        raise D3xxBackendError(function, value)


def _status_buffer_and_transferred(function: str, result: object) -> tuple[int, object, int]:
    if not isinstance(result, tuple) or len(result) < 3:
        raise D3xxBackendError(function)
    return (
        _int_from_object(f"{function}.status", result[0]),
        result[1],
        _int_from_object(f"{function}.transferred", result[2]),
    )


def _status_and_transferred(function: str, result: object) -> tuple[int, int]:
    if not isinstance(result, tuple) or len(result) < 2:
        raise D3xxBackendError(function)
    return (
        _int_from_object(f"{function}.status", result[0]),
        _int_from_object(f"{function}.transferred", result[1]),
    )


def _pipe_from_id(binding: D3xxBinding, pipe: int) -> object:
    pipe_type = binding.FT_Pipe
    pipe_object = pipe_type()
    pipe_object.PipeID = pipe
    pipe_object._PipeID = pipe
    return pipe_object


def _buffer_from_bytes(binding: D3xxBinding, payload: bytes) -> object:
    buffer_type = binding.FT_Buffer
    return buffer_type.from_bytes(payload)


def _buffer_value(buffer: object) -> bytearray:
    value_method = cast("Any", buffer).Value
    if not callable(value_method):
        raise D3xxBackendError("FT_Buffer.Value")
    value = value_method()
    if isinstance(value, bytearray):
        return value
    if isinstance(value, bytes):
        return bytearray(value)
    raise D3xxBackendError("FT_Buffer.Value")


def _direct_write_pipe(
    binding: D3xxBinding,
    device: object,
    pipe: int,
    payload: bytes,
    timeout_ms: int,
) -> int | None:
    dll = _pyd3xx_dll(binding)
    if dll is None:
        return None
    dll = cast("Any", dll)
    buffer = ctypes.create_string_buffer(payload, len(payload))
    transferred = ctypes.c_ulong(0)
    handle = _device_handle(device)
    with _pipe_timeout(dll, handle, pipe, timeout_ms):
        status = dll.FT_WritePipe(
            handle,
            ctypes.c_ubyte(pipe),
            buffer,
            ctypes.c_ulong(len(payload)),
            ctypes.byref(transferred),
            None,
        )
    _check_status("FT_WritePipe", status)
    return int(transferred.value)


def _direct_read_pipe(
    binding: D3xxBinding,
    device: object,
    pipe: int,
    length: int,
    timeout_ms: int,
) -> bytes | None:
    dll = _pyd3xx_dll(binding)
    if dll is None:
        return None
    dll = cast("Any", dll)
    buffer = ctypes.create_string_buffer(length)
    transferred = ctypes.c_ulong(0)
    handle = _device_handle(device)
    with _pipe_timeout(dll, handle, pipe, timeout_ms):
        status = dll.FT_ReadPipe(
            handle,
            ctypes.c_ubyte(pipe),
            buffer,
            ctypes.c_ulong(length),
            ctypes.byref(transferred),
            None,
        )
    _check_status("FT_ReadPipe", status)
    return bytes(buffer.raw[: transferred.value])


def _direct_read_pipe_ex(
    binding: D3xxBinding,
    device: object,
    pipe: int,
    length: int,
    timeout_ms: int,
) -> bytes | None:
    dll = _pyd3xx_dll(binding)
    if dll is None:
        return None
    dll = cast("Any", dll)
    buffer = ctypes.create_string_buffer(length)
    transferred = ctypes.c_ulong(0)
    handle = _device_handle(device)
    with _pipe_timeout(dll, handle, pipe, timeout_ms):
        status = dll.FT_ReadPipeEx(
            handle,
            ctypes.c_ubyte(pipe),
            buffer,
            ctypes.c_ulong(length),
            ctypes.byref(transferred),
            None,
        )
    _check_status("FT_ReadPipeEx", status)
    return bytes(buffer.raw[: transferred.value])


@contextmanager
def _pipe_timeout(dll: object, handle: object, pipe: int, timeout_ms: int) -> Iterator[None]:
    dll = cast("Any", dll)
    old_timeout_ms = ctypes.c_ulong(0)
    status = dll.FT_GetPipeTimeout(handle, ctypes.c_ubyte(pipe), ctypes.byref(old_timeout_ms))
    _check_status("FT_GetPipeTimeout", status)
    status = dll.FT_SetPipeTimeout(handle, ctypes.c_ubyte(pipe), ctypes.c_ulong(timeout_ms))
    _check_status("FT_SetPipeTimeout", status)
    try:
        yield
    finally:
        status = dll.FT_SetPipeTimeout(handle, ctypes.c_ubyte(pipe), old_timeout_ms)
        _check_status("FT_SetPipeTimeout", status)


def _pyd3xx_dll(binding: D3xxBinding) -> object | None:
    if not isinstance(binding, ModuleType):
        return None
    try:
        implementation = import_module("PyD3XX.PyD3XX")
    except ImportError:
        return None
    return getattr(implementation, "_DLL", None)


def _device_handle(device: object) -> object:
    try:
        return cast("Any", device)._Handle
    except AttributeError as exc:
        raise D3xxBackendError.missing_field("_Handle") from exc


def _field(target: object, name: str) -> object:
    if isinstance(target, Mapping):
        mapping = cast("Mapping[str, object]", target)
        if name in mapping:
            return mapping[name]
        raise D3xxBackendError.missing_field(name)
    try:
        return getattr(target, name)
    except AttributeError as exc:
        raise D3xxBackendError.missing_field(name) from exc


def _vid_pid_from_device_id(device_id: int) -> tuple[int, int]:
    high = (device_id >> 16) & 0xFFFF
    low = device_id & 0xFFFF
    if high == N3DSXL_VENDOR_ID:
        return high, low
    if low == N3DSXL_VENDOR_ID:
        return low, high
    return high, low


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text == "":
        return None
    return text


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return _int_from_object("optional int", value)


def _int_from_object(field_name: str, value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str | bytes | bytearray):
        return int(value)
    raise D3xxBackendError.invalid_integer(field_name)


def _d3xx_error_message(function: str, status: int | None, field_name: str | None) -> str:
    if field_name is not None:
        return f"{function}: {field_name}"
    if status is None:
        return function
    return f"{function} failed with status {status}"
