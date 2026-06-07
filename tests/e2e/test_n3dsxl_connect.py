import os
from typing import TYPE_CHECKING, cast

import pytest

from py3dscapture.devices.n3dsxl_ftd3 import list_n3dsxl_devices
from py3dscapture.protocol.n3dsxl import N3DSXLProtocol
from py3dscapture.transport.d3xx_backend import D3xxBackend
from py3dscapture.transport.ftd3_backend import open_ftd3_transport
from py3dscapture.transport.libusb_backend import Usb1Backend

if TYPE_CHECKING:
    from py3dscapture.protocol.n3dsxl import N3DSXLPipe


@pytest.mark.requires_n3dsxl
def test_n3dsxl_connect_2d_default() -> None:
    if os.environ.get("PONKAN_HARDWARE_APPROVED") != "1":
        pytest.skip("set PONKAN_HARDWARE_APPROVED=1 after reviewing the hardware command scope")

    backend = Usb1Backend()
    listing = list_n3dsxl_devices(backend)
    assert listing.candidates, "no N3DSXL candidate found"

    transport = open_ftd3_transport(listing.candidates[0], backend, D3xxBackend())
    try:
        protocol = N3DSXLProtocol(transport, cast("N3DSXLPipe", transport))
        protocol.connect(mode_3d=False)
    finally:
        transport.close()
