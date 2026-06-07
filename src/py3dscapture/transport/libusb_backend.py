"""Thin libusb backend boundary used by device-specific code."""

from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING, Protocol, cast

from py3dscapture.errors import DeviceOpenError

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class UsbDeviceInfo:
    """USB descriptor fields needed before opening a capture device."""

    bus_number: int | None
    address: int | None
    vendor_id: int
    product_id: int
    product_string: str | None
    serial_number: str | None = None


class UsbHandle(Protocol):
    """Opened USB handle primitive."""

    def detach_kernel_driver(self, interface: int) -> None:
        """Detach the kernel driver for an interface when supported."""
        ...

    def set_configuration(self, configuration: int) -> None:
        """Select a USB configuration."""
        ...

    def claim_interface(self, interface: int) -> None:
        """Claim a USB interface."""
        ...

    def release_interface(self, interface: int) -> None:
        """Release a USB interface."""
        ...

    def close(self) -> None:
        """Close the device handle."""
        ...

    def bulk_write(self, endpoint: int, payload: bytes, timeout_ms: int) -> int:
        """Write bytes to a bulk endpoint and return transferred bytes."""
        ...

    def bulk_read(self, endpoint: int, length: int, timeout_ms: int) -> bytes:
        """Read bytes from a bulk endpoint."""
        ...


class LibusbBackend(Protocol):
    """Device enumeration and opening primitive."""

    def iter_devices(self) -> Iterable[UsbDeviceInfo]:
        """Iterate devices visible through the backend."""
        ...

    def open(self, device: UsbDeviceInfo) -> UsbHandle:
        """Open one device descriptor."""
        ...


class Usb1Backend:
    """libusb1-backed implementation."""

    def iter_devices(self) -> list[UsbDeviceInfo]:
        """Return devices visible through libusb1."""
        usb1 = import_module("usb1")
        context_factory = cast("Callable[[], object]", usb1.USBContext)
        context = context_factory()
        try:
            devices = cast(
                "Iterable[object]",
                _call_method(context, "getDeviceList", skip_on_error=True),
            )
            return [_usb1_device_info(device) for device in devices]
        finally:
            _call_method(context, "close")

    def open(self, device: UsbDeviceInfo) -> UsbHandle:
        """Open a USB device by descriptor identity."""
        usb1 = import_module("usb1")
        context_factory = cast("Callable[[], object]", usb1.USBContext)
        context = context_factory()
        devices = cast(
            "Iterable[object]",
            _call_method(context, "getDeviceList", skip_on_error=True),
        )
        for candidate in devices:
            if _matches_usb1_device(candidate, device):
                try:
                    return _Usb1Handle(context=context, handle=_call_method(candidate, "open"))
                except Exception as exc:
                    _call_method(context, "close")
                    raise DeviceOpenError from exc

        _call_method(context, "close")
        raise DeviceOpenError


class _Usb1Handle:
    def __init__(self, context: object, handle: object) -> None:
        self._context = context
        self._handle = handle
        self._closed = False

    def detach_kernel_driver(self, interface: int) -> None:
        try:
            active = bool(_call_method(self._handle, "kernelDriverActive", interface))
        except AttributeError:
            return
        if active:
            _call_method(self._handle, "detachKernelDriver", interface)

    def set_configuration(self, configuration: int) -> None:
        _call_method(self._handle, "setConfiguration", configuration)

    def claim_interface(self, interface: int) -> None:
        _call_method(self._handle, "claimInterface", interface)

    def release_interface(self, interface: int) -> None:
        _call_method(self._handle, "releaseInterface", interface)

    def close(self) -> None:
        if self._closed:
            return
        try:
            _call_method(self._handle, "close")
        finally:
            _call_method(self._context, "close")
            self._closed = True

    def bulk_write(self, endpoint: int, payload: bytes, timeout_ms: int) -> int:
        transferred = _call_method(self._handle, "bulkWrite", endpoint, payload, timeout_ms)
        return _int_from_object(transferred)

    def bulk_read(self, endpoint: int, length: int, timeout_ms: int) -> bytes:
        data = _call_method(self._handle, "bulkRead", endpoint, length, timeout_ms)
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray | memoryview):
            return bytes(data)
        raise TypeError


def _usb1_device_info(device: object) -> UsbDeviceInfo:
    return UsbDeviceInfo(
        bus_number=_optional_int(device, "getBusNumber"),
        address=_optional_int(device, "getDeviceAddress"),
        vendor_id=_int_from_object(_call_method(device, "getVendorID")),
        product_id=_int_from_object(_call_method(device, "getProductID")),
        product_string=_usb1_product_string(device),
        serial_number=_optional_str(device, "getSerialNumber"),
    )


def _usb1_product_string(device: object) -> str | None:
    product = _usb1_product_string_from_handle(device)
    if product is not None:
        return product
    return _optional_str(device, "getProduct")


def _usb1_product_string_from_handle(device: object) -> str | None:
    try:
        descriptor = _int_from_object(_call_method(device, "getProductDescriptor"))
    except (AttributeError, TypeError, ValueError):
        return None
    if descriptor == 0:
        return None

    try:
        handle = _call_method(device, "open")
    except Exception:  # noqa: BLE001
        return None
    try:
        product = _optional_str(handle, "getProduct")
        if product is not None:
            return product
        for language_id in _usb1_language_ids(handle):
            product = _optional_string_descriptor(handle, descriptor, language_id)
            if product is not None:
                return product
    finally:
        with suppress(Exception):
            _call_method(handle, "close")
    return None


def _usb1_language_ids(handle: object) -> tuple[int, ...]:
    try:
        values = _call_method(handle, "getSupportedLanguageList")
    except Exception:  # noqa: BLE001
        return (0x0409,)
    try:
        language_ids = tuple(_int_from_object(value) for value in cast("Iterable[object]", values))
    except (TypeError, ValueError):
        return (0x0409,)
    return language_ids or (0x0409,)


def _optional_string_descriptor(
    handle: object,
    descriptor: int,
    language_id: int,
) -> str | None:
    try:
        value = _call_method(handle, "getStringDescriptor", descriptor, language_id)
    except Exception:  # noqa: BLE001
        return None
    if value == "":
        return None
    return str(value)


def _matches_usb1_device(candidate: object, expected: UsbDeviceInfo) -> bool:
    candidate_info = _usb1_device_info(candidate)
    if expected.bus_number is not None and candidate_info.bus_number != expected.bus_number:
        return False
    if expected.address is not None and candidate_info.address != expected.address:
        return False
    return (
        candidate_info.vendor_id == expected.vendor_id
        and candidate_info.product_id == expected.product_id
        and candidate_info.product_string == expected.product_string
        and candidate_info.serial_number == expected.serial_number
    )


def _optional_int(device: object, method_name: str) -> int | None:
    try:
        return _int_from_object(_call_method(device, method_name))
    except (AttributeError, TypeError, ValueError):
        return None


def _optional_str(device: object, method_name: str) -> str | None:
    try:
        value = _call_method(device, method_name)
    except Exception:  # noqa: BLE001
        return None
    if value == "":
        return None
    return str(value)


def _call_method(
    target: object,
    method_name: str,
    *args: object,
    **kwargs: object,
) -> object:
    method = getattr(target, method_name)
    if not callable(method):
        raise TypeError
    return method(*args, **kwargs)


def _int_from_object(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str | bytes | bytearray):
        return int(value)
    raise TypeError
