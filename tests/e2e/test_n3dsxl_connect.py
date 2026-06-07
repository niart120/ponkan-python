import os

import pytest

from py3dscapture.devices.n3dsxl_ftd3 import N3DSXLDevice, list_n3dsxl_devices
from py3dscapture.protocol.n3dsxl import N3DSXLProtocol
from py3dscapture.transport.ftd3_pipe import Ftd3Pipe
from py3dscapture.transport.libusb_backend import Usb1Backend


@pytest.mark.requires_n3dsxl
def test_n3dsxl_connect_2d_default() -> None:
    if os.environ.get("PONKAN_HARDWARE_APPROVED") != "1":
        pytest.skip("set PONKAN_HARDWARE_APPROVED=1 after reviewing the hardware command scope")

    backend = Usb1Backend()
    listing = list_n3dsxl_devices(backend)
    assert listing.candidates, "no N3DSXL candidate found"

    with N3DSXLDevice.open(listing.candidates[0], backend=backend) as device:
        protocol = N3DSXLProtocol(device, Ftd3Pipe(device))
        protocol.connect(mode_3d=False)
