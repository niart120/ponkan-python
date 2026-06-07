from py3dscapture.devices.n3dsxl_ftd3 import DeviceCandidate, RejectedDevice, classify_n3dsxl_device
from py3dscapture.transport.libusb_backend import UsbDeviceInfo


def device_info(
    *,
    vendor_id: int = 0x0403,
    product_id: int = 0x601F,
    product_string: str | None = "N3DSXL",
) -> UsbDeviceInfo:
    return UsbDeviceInfo(
        bus_number=1,
        address=2,
        vendor_id=vendor_id,
        product_id=product_id,
        product_string=product_string,
        serial_number="abc",
    )


def test_accepted_vid_pid_product_string_becomes_candidate() -> None:
    classified = classify_n3dsxl_device(device_info())

    assert isinstance(classified, DeviceCandidate)
    assert classified.product_string == "N3DSXL"
    assert classified.product_string_status == "accepted"
    assert classified.model == "new_3ds_xl"


def test_n3dsxl_dot_2_product_string_becomes_candidate() -> None:
    classified = classify_n3dsxl_device(device_info(product_string="N3DSXL.2"))

    assert isinstance(classified, DeviceCandidate)
    assert classified.product_string == "N3DSXL.2"
    assert classified.product_string_status == "accepted"


def test_accepted_pid_with_wrong_product_string_is_rejected() -> None:
    classified = classify_n3dsxl_device(device_info(product_string="FT232H"))

    assert isinstance(classified, RejectedDevice)
    assert classified.reason == "unsupported_product_string"


def test_unreadable_product_string_becomes_candidate() -> None:
    classified = classify_n3dsxl_device(device_info(product_string=None))

    assert isinstance(classified, DeviceCandidate)
    assert classified.product_string is None
    assert classified.product_string_status == "unreadable"


def test_non_ftdi_device_is_ignored() -> None:
    classified = classify_n3dsxl_device(device_info(vendor_id=0x16D0, product_id=0x06A3))

    assert classified is None
