import os
from pathlib import Path

import pytest

from py3dscapture.artifacts import n3dsxl_artifact_dir, write_json_artifact
from py3dscapture.hardware_gate import hardware_approved
from py3dscapture.streaming.engine import StreamingEngine
from py3dscapture.tools.stream_n3dsxl import run_streaming_smoke
from py3dscapture.transport.libusb_async import LibusbAsyncBackend


@pytest.mark.requires_n3dsxl
@pytest.mark.performance
def test_n3dsxl_streaming_60_second_performance_smoke(tmp_path: Path) -> None:
    if not hardware_approved(os.environ):
        pytest.skip("set PONKAN_HARDWARE_APPROVED=1 after reviewing the hardware command scope")

    engine = StreamingEngine(LibusbAsyncBackend())
    stats = run_streaming_smoke(
        engine,
        duration=60.0,
        noop_consumer=True,
        product_string=os.environ.get("PONKAN_N3DSXL_PRODUCT_STRING", "N3DSXL"),
        product_string_status="accepted",
        mode_3d=False,
        raw_slots=4,
        output_queue_size=2,
        drop_policy="drop_oldest",
    )
    stats_path = n3dsxl_artifact_dir("performance-smoke", root=tmp_path) / "stream_stats.json"
    write_json_artifact(stats_path, stats.to_dict())

    assert stats.duration_seconds == 60.0
    assert stats.usb_errors == 0
    assert stats.shutdown_seconds <= 2.0
    assert stats.delivered_fps >= 50.0
