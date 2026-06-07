from py3dscapture.devices.n3dsxl_ftd3 import list_n3dsxl_devices
from py3dscapture.tools.list_devices import format_device_listing
from py3dscapture.transport.libusb_backend import UsbDeviceInfo


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

    def bulk_write(self, endpoint: int, payload: bytes, timeout_ms: int) -> int:
        _ = endpoint, payload, timeout_ms
        raise AssertionError

    def bulk_read(self, endpoint: int, length: int, timeout_ms: int) -> bytes:
        _ = endpoint, length, timeout_ms
        raise AssertionError


class _FakeBackend:
    def iter_devices(self) -> list[UsbDeviceInfo]:
        return [
            UsbDeviceInfo(1, 2, 0x0403, 0x601F, "N3DSXL", "abc"),
            UsbDeviceInfo(1, 4, 0x0403, 0x601E, None, "nxl"),
            UsbDeviceInfo(1, 3, 0x0403, 0x601F, "FT232H", "def"),
        ]

    def open(self, device: UsbDeviceInfo) -> _UnusedHandle:
        _ = device
        raise AssertionError


def test_list_devices_classifies_without_opening() -> None:
    listing = list_n3dsxl_devices(_FakeBackend())

    assert len(listing.candidates) == 2
    assert len(listing.rejected) == 1
    assert listing.candidates[1].product_string_status == "unreadable"
    assert listing.rejected[0].reason == "unsupported_product_string"


def test_format_device_listing_shows_candidate_and_rejected_reason() -> None:
    listing = list_n3dsxl_devices(_FakeBackend())

    output = format_device_listing(listing)

    assert "N3DSXL" in output
    assert "product=- product_status=unreadable" in output
    assert "0x0403:0x601f" in output
    assert "unsupported_product_string" in output
