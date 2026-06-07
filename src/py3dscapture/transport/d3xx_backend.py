# ruff: noqa: N802
"""Optional FTDI D3XX backend boundary."""

import ctypes
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from types import ModuleType
from typing import Any, Protocol, cast

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
    """Subset of the PyD3XX module needed for device enumeration."""

    FT_Pipe: Any
    FT_Buffer: Any

    def FT_CreateDeviceInfoList(self) -> tuple[int, int]:
        """Return D3XX status and number of devices."""
        ...

    def FT_GetDeviceInfoDetail(self, index: int) -> tuple[int, object]:
        """Return D3XX status and one device information node."""
        ...

    def FT_Create(self, identifier: object, open_flag: int, device: object) -> int:
        """Open a D3XX device into an initialized FT_Device object."""
        ...

    def FT_Close(self, device: object) -> int:
        """Close an opened D3XX device object."""
        ...

    def FT_AbortPipe(self, device: object, pipe: object) -> int:
        """Abort one D3XX native pipe."""
        ...

    def FT_SetStreamPipe(
        self,
        device: object,
        all_write_pipes: bool,
        all_read_pipes: bool,
        pipe: object,
        stream_size: int,
    ) -> int:
        """Configure streaming for one D3XX native pipe."""
        ...

    def FT_ReadPipe(
        self,
        device: object,
        pipe: object,
        buffer_length: int,
        overlapped_timeout_ms: int,
    ) -> tuple[int, object, int]:
        """Read bytes from one D3XX native pipe."""
        ...

    def FT_WritePipe(
        self,
        device: object,
        pipe: object,
        buffer: object,
        buffer_length: int,
        overlapped_timeout_ms: int,
    ) -> tuple[int, int]:
        """Write bytes to one D3XX native pipe."""
        ...


class D3xxBackendError(CaptureError):
    """Raised when a D3XX API call fails or returns unsupported data."""

    def __init__(
        self,
        function: str,
        status: int | None = None,
        *,
        field_name: str | None = None,
    ) -> None:
        """Create a structured D3XX backend failure."""
        message = _d3xx_error_message(function, status, field_name)
        super().__init__(message)
        self.function = function
        self.status = status
        self.field_name = field_name

    @classmethod
    def missing_field(cls, field_name: str) -> "D3xxBackendError":
        """Create an error for an unsupported D3XX detail shape."""
        return cls("missing field", field_name=field_name)

    @classmethod
    def invalid_integer(cls, field_name: str) -> "D3xxBackendError":
        """Create an error for an integer field that cannot be parsed."""
        return cls("invalid integer", field_name=field_name)


@dataclass(frozen=True, slots=True)
class D3xxDeviceInfo:
    """D3XX listing information normalized for N3DSXL classification."""

    index: int
    usb_info: UsbDeviceInfo
    flags: int | None
    device_id: int


@dataclass(frozen=True, slots=True)
class D3xxDeviceCandidate:
    """N3DSXL candidate found through the D3XX driver backend."""

    candidate: DeviceCandidate
    index: int
    flags: int | None
    device_id: int
    backend_kind: str = "d3xx"


class D3xxHandle:
    """Opened D3XX handle with idempotent close."""

    backend_kind = "d3xx"

    def __init__(self, binding: D3xxBinding, device: object, candidate: DeviceCandidate) -> None:
        """Create a handle from an opened PyD3XX device detail object."""
        self._binding = binding
        self._device = device
        self.candidate = candidate
        self._closed = False

    def close(self) -> None:
        """Close the D3XX device handle."""
        if self._closed:
            return
        try:
            _check_status("FT_Close", self._binding.FT_Close(self._device))
        finally:
            self._closed = True

    def abort_pipe(self, pipe: int) -> None:
        """Abort one D3XX native pipe."""
        pipe_object = _pipe_from_id(self._binding, pipe)
        _check_status("FT_AbortPipe", self._binding.FT_AbortPipe(self._device, pipe_object))

    def create_pipe(self) -> None:
        """Keep protocol compatibility; D3XX native backend has no command-pipe create."""

    def set_stream_pipe(self, pipe: int, length: int) -> None:
        """Configure one D3XX native stream pipe."""
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

    def read_pipe(
        self,
        pipe: int,
        length: int,
        timeout_ms: int = D3XX_DEFAULT_TIMEOUT_MS,
    ) -> bytes:
        """Read bytes from one D3XX native pipe."""
        direct = _direct_read_pipe(self._binding, self._device, pipe, length)
        if direct is not None:
            return direct
        pipe_object = _pipe_from_id(self._binding, pipe)
        result = self._binding.FT_ReadPipe(self._device, pipe_object, length, timeout_ms)
        status, buffer, transferred = _status_buffer_and_transferred("FT_ReadPipe", result)
        _check_status("FT_ReadPipe", status)
        return bytes(_buffer_value(buffer)[:transferred])

    def write_pipe(
        self,
        pipe: int,
        payload: bytes,
        timeout_ms: int = D3XX_DEFAULT_TIMEOUT_MS,
    ) -> int:
        """Write bytes to one D3XX native pipe."""
        direct = _direct_write_pipe(self._binding, self._device, pipe, payload)
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
    """Import the optional PyD3XX module."""
    for module_name in PYD3XX_MODULE_NAMES:
        try:
            return cast("D3xxBinding", import_module(module_name))
        except ImportError:
            continue
    raise OptionalDependencyError("PyD3XX", "d3xx")


class D3xxBackend:
    """FTDI D3XX-backed device enumeration."""

    def __init__(self, binding: D3xxBinding | None = None) -> None:
        """Create a backend using an injected or optional PyD3XX binding."""
        self._binding = binding or load_pyd3xx_binding()

    def iter_devices(self) -> tuple[D3xxDeviceInfo, ...]:
        """Return D3XX devices visible through the binding."""
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
        """Return N3DSXL candidates visible through the D3XX backend."""
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

    def open(self, candidate: D3xxDeviceCandidate) -> D3xxHandle:
        """Open one D3XX candidate and return a closeable handle."""
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
        return D3xxHandle(binding=self._binding, device=detail, candidate=candidate.candidate)


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
) -> int | None:
    dll = _pyd3xx_dll(binding)
    if dll is None:
        return None
    dll = cast("Any", dll)
    buffer = ctypes.create_string_buffer(payload, len(payload))
    transferred = ctypes.c_ulong(0)
    status = dll.FT_WritePipe(
        _device_handle(device),
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
) -> bytes | None:
    dll = _pyd3xx_dll(binding)
    if dll is None:
        return None
    dll = cast("Any", dll)
    buffer = ctypes.create_string_buffer(length)
    transferred = ctypes.c_ulong(0)
    status = dll.FT_ReadPipe(
        _device_handle(device),
        ctypes.c_ubyte(pipe),
        buffer,
        ctypes.c_ulong(length),
        ctypes.byref(transferred),
        None,
    )
    _check_status("FT_ReadPipe", status)
    return bytes(buffer.raw[: transferred.value])


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
