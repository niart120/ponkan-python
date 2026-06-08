"""Capture one raw N3DSXL frame to a fixture pair."""

import argparse
from pathlib import Path

from py3dscapture.capture import save_raw_capture
from py3dscapture.devices.n3dsxl_ftd3 import N3DSXLDevice, list_n3dsxl_devices
from py3dscapture.protocol.n3dsxl import N3DSXLProtocol
from py3dscapture.transport.ftd3_pipe import Ftd3Pipe
from py3dscapture.transport.libusb_backend import Usb1Backend


def main(argv: list[str] | None = None) -> int:
    """Run the raw-capture CLI.

    Args:
        argv: Optional command-line arguments. ``None`` uses ``sys.argv`` through
            ``argparse``.

    Returns:
        Process status code. Zero means the raw payload and metadata sidecar were
        written.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["new_3ds_xl"], default="new_3ds_xl")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    backend = Usb1Backend()
    listing = list_n3dsxl_devices(backend)
    if not listing.candidates:
        parser.error("no N3DSXL candidate found")

    with N3DSXLDevice.open(listing.candidates[0], backend=backend) as device:
        protocol = N3DSXLProtocol(device, Ftd3Pipe(device))
        protocol.connect(mode_3d=False)
        capture = protocol.read_raw_frame(mode_3d=False)
    save_raw_capture(capture, args.out, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
