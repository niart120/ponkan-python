import pytest

import ponkan
from ponkan.errors import DependencyUnavailableError
from ponkan.transport.libusb_backend import UsbDeviceInfo


class _UnusedHandle:
    def detach_kernel_driver(self, interface: int) -> None:
        _ = interface
        raise AssertionError

    def set_configuration(self, configuration: int) -> None:
        _ = configuration
        raise AssertionError

    def claim_interface(self, interface: int) -> None:
        _ = interface
        raise AssertionError

    def release_interface(self, interface: int) -> None:
        _ = interface
        raise AssertionError

    def close(self) -> None:
        raise AssertionError


class _FakeLibusbBackend:
    def __init__(self) -> None:
        self.opened: list[UsbDeviceInfo] = []

    def iter_devices(self) -> tuple[UsbDeviceInfo, ...]:
        return (
            UsbDeviceInfo(1, 2, 0x0403, 0x601F, "N3DSXL", "abc"),
            UsbDeviceInfo(1, 4, 0x0403, 0x601E, None, "nxl"),
            UsbDeviceInfo(1, 3, 0x0403, 0x601F, "FT232H", "def"),
        )

    def open(self, device: UsbDeviceInfo) -> _UnusedHandle:
        self.opened.append(device)
        raise AssertionError


class _NoSerialLibusbBackend:
    def iter_devices(self) -> tuple[UsbDeviceInfo, ...]:
        return (UsbDeviceInfo(7, 9, 0x0403, 0x601F, "N3DSXL", None),)


def test_windows_auto_resolves_to_d3xx_native_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ponkan.devices.discovery as discovery_module  # noqa: PLC0415

    def missing_backend() -> object:
        raise DependencyUnavailableError.for_backend_dependency("PyD3XX", "d3xx-native")

    monkeypatch.setattr(discovery_module, "_new_d3xx_backend", missing_backend)

    result = discovery_module.list_capture_devices(backend="auto", _sys_platform="win32")

    assert result.backend_preference == "auto"
    assert result.resolved_backend == "d3xx-native"
    assert result.backend_status == "unavailable"
    assert result.reason == "missing_package"
    assert result.devices == ()


def test_libusb_discovery_maps_accepted_unreadable_and_rejected_devices() -> None:
    from ponkan.devices.discovery import list_capture_devices  # noqa: PLC0415

    backend = _FakeLibusbBackend()

    result = list_capture_devices(
        backend="libusb",
        include_rejected=True,
        _libusb_backend=backend,
    )

    assert result.profile_id == "n3dsxl"
    assert result.resolved_backend == "libusb"
    assert result.backend_status == "available"
    assert result.reason == "available"
    assert backend.opened == []

    accepted, unreadable, rejected = result.devices
    assert accepted.id == "libusb:abc"
    assert accepted.connection_status == "available"
    assert accepted.product_string_status == "accepted"
    assert accepted.reason == "available"

    assert unreadable.id == "libusb:nxl"
    assert unreadable.connection_status == "available"
    assert unreadable.product_string_status == "unreadable"

    assert rejected.id == "libusb:def"
    assert rejected.connection_status == "rejected"
    assert rejected.product_string_status == "rejected"
    assert rejected.reason == "device_rejected"


def test_libusb_discovery_marks_serial_and_session_id_stability() -> None:
    from ponkan.devices.discovery import list_capture_devices  # noqa: PLC0415

    serial_result = list_capture_devices(
        backend="libusb",
        _libusb_backend=_FakeLibusbBackend(),
    )
    session_result = list_capture_devices(
        backend="libusb",
        _libusb_backend=_NoSerialLibusbBackend(),
    )

    assert serial_result.devices[0].id == "libusb:abc"
    assert serial_result.devices[0].id_stability == "stable"
    assert session_result.devices[0].id == "libusb:bus7:address9"
    assert session_result.devices[0].id_stability == "session"


def test_rejected_devices_are_hidden_by_default() -> None:
    from ponkan.devices.discovery import list_capture_devices  # noqa: PLC0415

    result = list_capture_devices(backend="libusb", _libusb_backend=_FakeLibusbBackend())

    assert [device.connection_status for device in result.devices] == [
        "available",
        "available",
    ]


def test_unknown_profile_returns_unsupported_discovery_result() -> None:
    from ponkan.devices.discovery import list_capture_devices  # noqa: PLC0415

    result = list_capture_devices(profile="classic_ds", backend="libusb")

    assert result.profile_id == "classic_ds"
    assert result.backend_status == "unsupported"
    assert result.reason == "unsupported_profile"
    assert result.devices == ()


def test_package_root_exports_discovery_api() -> None:
    assert "CaptureDeviceDiscovery" in ponkan.__all__
    assert "CaptureDeviceInfo" in ponkan.__all__
    assert "list_capture_devices" in ponkan.__all__
