import os

import pytest

from ponkan.devices.n3dsxl_ftd3 import list_n3dsxl_devices
from ponkan.protocol.sizes import N3DSXL_BULK_IN_ENDPOINT
from ponkan.transport.d3xx_backend import D3xxBackend
from ponkan.transport.ftd3_backend import open_ftd3_transport
from ponkan.transport.libusb_backend import Usb1Backend


@pytest.mark.requires_n3dsxl
def test_n3dsxl_ftd3_create_abort() -> None:
    if os.environ.get("PONKAN_HARDWARE_APPROVED") != "1":
        pytest.skip("set PONKAN_HARDWARE_APPROVED=1 after reviewing the hardware command scope")

    backend = Usb1Backend()
    listing = list_n3dsxl_devices(backend)
    assert listing.candidates, "no N3DSXL candidate found"

    transport = open_ftd3_transport(listing.candidates[0], backend, D3xxBackend())
    try:
        transport.create_pipe()
        transport.abort_pipe(N3DSXL_BULK_IN_ENDPOINT)
    finally:
        transport.close()
