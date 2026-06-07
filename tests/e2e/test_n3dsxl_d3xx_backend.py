import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from py3dscapture.capture import save_raw_capture
from py3dscapture.devices.n3dsxl_ftd3 import list_n3dsxl_devices
from py3dscapture.protocol.n3dsxl import N3DSXLProtocol
from py3dscapture.protocol.sizes import N3DSXL_BULK_IN_ENDPOINT
from py3dscapture.transport.d3xx_backend import D3xxBackend, D3xxDeviceCandidate, D3xxDeviceInfo
from py3dscapture.transport.ftd3_backend import open_ftd3_transport
from py3dscapture.transport.libusb_backend import Usb1Backend

if TYPE_CHECKING:
    from py3dscapture.protocol.n3dsxl import N3DSXLPipe
    from py3dscapture.transport.ftd3_backend import D3xxFallbackBackend

pytestmark = pytest.mark.requires_n3dsxl


def _require_hardware_approval() -> None:
    if os.environ.get("PONKAN_HARDWARE_APPROVED") != "1":
        pytest.skip("set PONKAN_HARDWARE_APPROVED=1 after reviewing the hardware command scope")


def _d3xx_candidate() -> tuple[D3xxBackend, D3xxDeviceCandidate]:
    backend = D3xxBackend()
    devices = backend.iter_devices()
    candidates = backend.iter_device_candidates()
    assert candidates, "no D3XX N3DSXL candidate found; " + _format_d3xx_devices(devices)
    return backend, candidates[0]


def _format_d3xx_devices(devices: tuple[D3xxDeviceInfo, ...]) -> str:
    if not devices:
        return "d3xx_device_count=0"
    parts = [f"d3xx_device_count={len(devices)}"]
    for device in devices:
        usb_info = device.usb_info
        parts.append(
            "device "
            f"index={device.index} "
            f"id=0x{device.device_id:08x} "
            f"vid=0x{usb_info.vendor_id:04x} "
            f"pid=0x{usb_info.product_id:04x} "
            f"product={usb_info.product_string or '-'} "
            f"serial={usb_info.serial_number or '-'} "
            f"flags={device.flags}"
        )
    return "; ".join(parts)


def test_n3dsxl_d3xx_open_close() -> None:
    _require_hardware_approval()
    backend, candidate = _d3xx_candidate()

    handle = backend.open(candidate)
    handle.close()


def test_n3dsxl_d3xx_native_pipe_setup() -> None:
    _require_hardware_approval()
    backend, candidate = _d3xx_candidate()

    handle = backend.open(candidate)
    try:
        handle.abort_pipe(N3DSXL_BULK_IN_ENDPOINT)
        handle.set_stream_pipe(N3DSXL_BULK_IN_ENDPOINT, 1024)
    finally:
        handle.close()


def test_n3dsxl_fallback_selector_uses_d3xx() -> None:
    _require_hardware_approval()
    libusb_backend = Usb1Backend()
    listing = list_n3dsxl_devices(libusb_backend)
    assert listing.candidates, "no libusb N3DSXL candidate found"

    transport = open_ftd3_transport(
        listing.candidates[0],
        libusb_backend,
        cast("D3xxFallbackBackend", D3xxBackend()),
    )
    try:
        assert transport.backend_kind == "d3xx"
    finally:
        transport.close()


def test_n3dsxl_d3xx_connect_2d_default() -> None:
    _require_hardware_approval()
    backend, candidate = _d3xx_candidate()

    handle = backend.open(candidate)
    try:
        protocol = N3DSXLProtocol(handle, cast("N3DSXLPipe", handle))
        protocol.connect(mode_3d=False)
    finally:
        handle.close()


def test_n3dsxl_d3xx_raw_capture_fixture(tmp_path: Path) -> None:
    _require_hardware_approval()
    backend, candidate = _d3xx_candidate()

    handle = backend.open(candidate)
    try:
        protocol = N3DSXLProtocol(handle, cast("N3DSXLPipe", handle))
        protocol.connect(mode_3d=False)
        capture = protocol.read_raw_frame(mode_3d=False)
    finally:
        handle.close()

    bin_path, metadata_path = save_raw_capture(capture, tmp_path / "raw_2d_d3xx_001.bin")
    assert bin_path.exists()
    assert metadata_path.exists()
    assert capture.metadata["backend_kind"] == "d3xx"
    assert capture.metadata["product_string"] == "N3DSXL.2"
    assert capture.transferred >= capture.video_size
