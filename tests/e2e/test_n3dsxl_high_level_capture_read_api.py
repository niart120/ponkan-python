import os
from pathlib import Path

import pytest

from ponkan import CaptureOutput, open_capture
from ponkan.artifacts import n3dsxl_artifact_dir, write_json_artifact
from ponkan.hardware_gate import hardware_approved


@pytest.mark.requires_n3dsxl
def test_n3dsxl_high_level_capture_read_api_smoke(tmp_path: Path) -> None:
    if not hardware_approved(os.environ):
        pytest.skip("set PONKAN_HARDWARE_APPROVED=1 after reviewing the hardware command scope")

    with open_capture(backend="d3xx", read_timeout=2.0) as cap:
        frame = cap.read_frame(timeout=2.0)
        assert frame is not None
        assert frame.top.shape == (240, 400, 3)
        assert frame.bottom.shape == (240, 320, 3)

        top = cap.read(output=CaptureOutput.TOP, timeout=2.0)
        bottom = cap.read(output=CaptureOutput.BOTTOM, timeout=2.0)
        both = cap.read(output=CaptureOutput.BOTH_VERTICAL, timeout=2.0)
        stats = cap.stats()

    assert top is not None
    assert bottom is not None
    assert both is not None
    assert top.shape == (240, 400, 3)
    assert bottom.shape == (240, 320, 3)
    assert both.shape == (480, 400, 3)
    assert stats.usb_errors == 0
    assert stats.decode_errors == 0
    stats_path = n3dsxl_artifact_dir("high-level-read-api", root=tmp_path) / "read_stats.json"
    write_json_artifact(
        stats_path,
        {
            "top_shape": top.shape,
            "bottom_shape": bottom.shape,
            "both_shape": both.shape,
            "stats": stats.to_dict(),
        },
    )
