import os

import pytest

from ponkan.devices.n3dsxl_ftd3 import list_n3dsxl_devices
from ponkan.transport.d3xx_backend import D3xxBackend
from ponkan.transport.ftd3_backend import open_ftd3_transport
from ponkan.transport.libusb_backend import Usb1Backend


@pytest.mark.requires_n3dsxl
def test_n3dsxl_open_claim_close_twice() -> None:
    if os.environ.get("PONKAN_HARDWARE_APPROVED") != "1":
        pytest.skip("set PONKAN_HARDWARE_APPROVED=1 after reviewing the hardware command scope")

    backend = Usb1Backend()
    listing = list_n3dsxl_devices(backend)
    assert listing.candidates, "no N3DSXL candidate found"

    for _ in range(2):
        transport = open_ftd3_transport(listing.candidates[0], backend, D3xxBackend())
        transport.close()
