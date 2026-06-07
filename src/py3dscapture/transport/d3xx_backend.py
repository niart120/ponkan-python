# ruff: noqa: N802
"""Optional FTDI D3XX backend boundary."""

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol, cast

from py3dscapture.devices.n3dsxl_ftd3 import DeviceCandidate, classify_n3dsxl_device
from py3dscapture.errors import CaptureError, OptionalDependencyError
from py3dscapture.protocol.sizes import N3DSXL_VENDOR_ID
from py3dscapture.transport.libusb_backend import UsbDeviceInfo

FT_OK = 0
D3XX_OPEN_BY_INDEX = 0x10
PYD3XX_MODULE_NAMES = ("PyD3XX", "pyd3xx")


class D3xxBinding(Protocol):
    """Subset of the PyD3XX module needed for device enumeration."""

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

    def __init__(self, binding: D3xxBinding, device: object) -> None:
        """Create a handle from an opened PyD3XX device detail object."""
        self._binding = binding
        self._device = device
        self._closed = False

    def close(self) -> None:
        """Close the D3XX device handle."""
        if self._closed:
            return
        try:
            _check_status("FT_Close", self._binding.FT_Close(self._device))
        finally:
            self._closed = True


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
            self._binding.FT_Create(candidate.index, D3XX_OPEN_BY_INDEX, detail),
        )
        return D3xxHandle(binding=self._binding, device=detail)


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
