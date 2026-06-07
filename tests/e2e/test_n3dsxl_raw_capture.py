import os
from pathlib import Path

import pytest

from py3dscapture.capture import save_raw_capture
from py3dscapture.devices.n3dsxl_ftd3 import N3DSXLDevice, list_n3dsxl_devices
from py3dscapture.protocol.n3dsxl import N3DSXLProtocol
from py3dscapture.transport.ftd3_pipe import Ftd3Pipe
from py3dscapture.transport.libusb_backend import Usb1Backend


@pytest.mark.requires_n3dsxl
def test_n3dsxl_raw_capture_fixture(tmp_path: Path) -> None:
    if os.environ.get("PONKAN_HARDWARE_APPROVED") != "1":
        pytest.skip("set PONKAN_HARDWARE_APPROVED=1 after reviewing the hardware command scope")

    backend = Usb1Backend()
    listing = list_n3dsxl_devices(backend)
    assert listing.candidates, "no N3DSXL candidate found"

    with N3DSXLDevice.open(listing.candidates[0], backend=backend) as device:
        protocol = N3DSXLProtocol(device, Ftd3Pipe(device))
        protocol.connect(mode_3d=False)
        capture = protocol.read_raw_frame(mode_3d=False)

    bin_path, metadata_path = save_raw_capture(capture, tmp_path / "raw_2d_001.bin")
    assert bin_path.exists()
    assert metadata_path.exists()
