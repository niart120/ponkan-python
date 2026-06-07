import os

import pytest

from py3dscapture.devices.n3dsxl_ftd3 import N3DSXLDevice, list_n3dsxl_devices
from py3dscapture.transport.libusb_backend import Usb1Backend


@pytest.mark.requires_n3dsxl
def test_n3dsxl_open_claim_close_twice() -> None:
    if os.environ.get("PONKAN_HARDWARE_APPROVED") != "1":
        pytest.skip("set PONKAN_HARDWARE_APPROVED=1 after reviewing the hardware command scope")

    backend = Usb1Backend()
    listing = list_n3dsxl_devices(backend)
    assert listing.candidates, "no N3DSXL candidate found"

    for _ in range(2):
        with N3DSXLDevice.open(listing.candidates[0], backend=backend):
            pass
