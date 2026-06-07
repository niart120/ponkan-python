import os

import pytest

from py3dscapture.devices.n3dsxl_ftd3 import N3DSXLDevice, list_n3dsxl_devices
from py3dscapture.protocol.sizes import N3DSXL_BULK_IN_ENDPOINT
from py3dscapture.transport.ftd3_pipe import Ftd3Pipe
from py3dscapture.transport.libusb_backend import Usb1Backend


@pytest.mark.requires_n3dsxl
def test_n3dsxl_ftd3_create_abort() -> None:
    if os.environ.get("PONKAN_HARDWARE_APPROVED") != "1":
        pytest.skip("set PONKAN_HARDWARE_APPROVED=1 after reviewing the hardware command scope")

    backend = Usb1Backend()
    listing = list_n3dsxl_devices(backend)
    assert listing.candidates, "no N3DSXL candidate found"

    with N3DSXLDevice.open(listing.candidates[0], backend=backend) as device:
        pipe = Ftd3Pipe(device)
        pipe.create_pipe()
        pipe.abort_pipe(N3DSXL_BULK_IN_ENDPOINT)
