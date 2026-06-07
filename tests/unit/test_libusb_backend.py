# ruff: noqa: N802

from py3dscapture.transport.libusb_backend import (
    UsbDeviceInfo,
    _matches_usb1_device,
    _usb1_device_info,
)


class _DescriptorHandle:
    def __init__(self, product: str = "N3DSXL.2") -> None:
        self.product = product
        self.closed = False

    def getProduct(self) -> str:
        raise RuntimeError

    def getSupportedLanguageList(self) -> list[int]:
        return [0x0411]

    def getStringDescriptor(self, descriptor: int, language_id: int) -> str:
        assert descriptor == 2
        assert language_id == 0x0411
        return self.product

    def close(self) -> None:
        self.closed = True


class _Usb1Device:
    def __init__(
        self,
        *,
        product_string: str | None = None,
        handle: _DescriptorHandle | None = None,
    ) -> None:
        self.product_string = product_string
        self.handle = handle

    def getBusNumber(self) -> int:
        return 7

    def getDeviceAddress(self) -> int:
        return 2

    def getVendorID(self) -> int:
        return 0x0403

    def getProductID(self) -> int:
        return 0x601E

    def getProduct(self) -> str:
        if self.product_string is None:
            raise RuntimeError
        return self.product_string

    def getProductDescriptor(self) -> int:
        return 2

    def getSerialNumber(self) -> str:
        return "NXL530228"

    def open(self) -> _DescriptorHandle:
        if self.handle is None:
            raise RuntimeError
        return self.handle


def test_usb1_device_info_reads_product_with_language_descriptor_fallback() -> None:
    handle = _DescriptorHandle()

    info = _usb1_device_info(_Usb1Device(handle=handle))

    assert info.product_string == "N3DSXL.2"
    assert handle.closed


def test_usb1_open_matching_rejects_readable_product_for_unreadable_expected() -> None:
    expected = UsbDeviceInfo(
        bus_number=7,
        address=2,
        vendor_id=0x0403,
        product_id=0x601E,
        product_string=None,
        serial_number="NXL530228",
    )

    assert not _matches_usb1_device(_Usb1Device(product_string="FT232H"), expected)


def test_usb1_open_matching_accepts_unreadable_expected_when_candidate_stays_unreadable() -> None:
    expected = UsbDeviceInfo(
        bus_number=7,
        address=2,
        vendor_id=0x0403,
        product_id=0x601E,
        product_string=None,
        serial_number="NXL530228",
    )

    assert _matches_usb1_device(_Usb1Device(), expected)
