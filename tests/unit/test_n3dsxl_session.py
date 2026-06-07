from collections.abc import Callable
from typing import cast

import pytest

from py3dscapture.devices.n3dsxl_ftd3 import DeviceCandidate, N3DSXLDevice, RejectedDevice
from py3dscapture.errors import UnsupportedDevice
from py3dscapture.transport.libusb_backend import UsbDeviceInfo


class _FakeHandle:
    def __init__(self, fail_on_claim: int | None = None) -> None:
        self.fail_on_claim = fail_on_claim
        self.calls: list[tuple[str, int | None]] = []

    def detach_kernel_driver(self, interface: int) -> None:
        self.calls.append(("detach", interface))

    def set_configuration(self, configuration: int) -> None:
        self.calls.append(("set_configuration", configuration))

    def claim_interface(self, interface: int) -> None:
        self.calls.append(("claim", interface))
        if interface == self.fail_on_claim:
            raise RuntimeError

    def release_interface(self, interface: int) -> None:
        self.calls.append(("release", interface))

    def close(self) -> None:
        self.calls.append(("close", None))

    def bulk_write(self, endpoint: int, payload: bytes, timeout_ms: int) -> int:
        _ = timeout_ms
        self.calls.append(("bulk_write", endpoint))
        return len(payload)

    def bulk_read(self, endpoint: int, length: int, timeout_ms: int) -> bytes:
        _ = timeout_ms
        self.calls.append(("bulk_read", endpoint))
        return bytes(length)


class _FakeBackend:
    def __init__(self, handle_factory: Callable[[], _FakeHandle] | None = None) -> None:
        self.handle_factory = handle_factory or _FakeHandle
        self.opened: list[UsbDeviceInfo] = []
        self.last_handle: _FakeHandle | None = None

    def iter_devices(self) -> list[UsbDeviceInfo]:
        return []

    def open(self, device: UsbDeviceInfo) -> _FakeHandle:
        self.opened.append(device)
        self.last_handle = self.handle_factory()
        return self.last_handle


def device_info() -> UsbDeviceInfo:
    return UsbDeviceInfo(
        bus_number=1,
        address=2,
        vendor_id=0x0403,
        product_id=0x601F,
        product_string="N3DSXL",
        serial_number="abc",
    )


def candidate() -> DeviceCandidate:
    return DeviceCandidate(info=device_info(), product_string="N3DSXL")


def test_open_sets_configuration_and_claims_command_then_bulk_interfaces() -> None:
    backend = _FakeBackend()

    device = N3DSXLDevice.open(candidate(), backend=backend)

    assert backend.last_handle is not None
    assert backend.last_handle.calls == [
        ("detach", 0),
        ("detach", 1),
        ("set_configuration", 1),
        ("claim", 0),
        ("claim", 1),
    ]
    assert device.candidate == candidate()


def test_interface_1_claim_failure_releases_interface_0_and_closes_handle() -> None:
    backend = _FakeBackend(lambda: _FakeHandle(fail_on_claim=1))

    with pytest.raises(RuntimeError):
        N3DSXLDevice.open(candidate(), backend=backend)

    assert backend.last_handle is not None
    assert backend.last_handle.calls == [
        ("detach", 0),
        ("detach", 1),
        ("set_configuration", 1),
        ("claim", 0),
        ("claim", 1),
        ("release", 0),
        ("close", None),
    ]


def test_close_is_idempotent() -> None:
    backend = _FakeBackend()

    device = N3DSXLDevice.open(candidate(), backend=backend)
    device.close()
    device.close()

    assert backend.last_handle is not None
    assert backend.last_handle.calls == [
        ("detach", 0),
        ("detach", 1),
        ("set_configuration", 1),
        ("claim", 0),
        ("claim", 1),
        ("release", 1),
        ("release", 0),
        ("close", None),
    ]


def test_rejected_device_cannot_be_opened() -> None:
    rejected = RejectedDevice(info=device_info(), reason="unsupported_product_string")

    with pytest.raises(UnsupportedDevice):
        N3DSXLDevice.open(cast("DeviceCandidate", rejected), backend=_FakeBackend())
