import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

import pytest

from py3dscapture.artifacts import n3dsxl_artifact_dir, write_json_artifact
from py3dscapture.hardware_gate import hardware_approved
from py3dscapture.protocol.n3dsxl import N3DSXLProtocol
from py3dscapture.streaming.engine import StreamingEngine
from py3dscapture.tools.stream_n3dsxl import run_streaming_smoke
from py3dscapture.transport.d3xx_backend import D3xxBackend
from py3dscapture.transport.d3xx_native_streaming import D3xxNativeFastPathBackend

if TYPE_CHECKING:
    from py3dscapture.protocol.n3dsxl import N3DSXLPipe


def _open_d3xx_native_streaming_engine() -> tuple[
    StreamingEngine,
    str | None,
    Literal["accepted", "unreadable"],
]:
    backend = D3xxBackend()
    candidates = backend.iter_device_candidates()
    if not candidates:
        pytest.skip("no D3XX N3DSXL candidate found")
    d3xx_candidate = candidates[0]
    handle = backend.open(d3xx_candidate)
    try:
        protocol = N3DSXLProtocol(handle, cast("N3DSXLPipe", handle))
        protocol.connect(mode_3d=False)
        engine = StreamingEngine(
            D3xxNativeFastPathBackend(handle),
            raw_slots=2,
            output_queue_size=2,
            drop_policy="drop_oldest",
            collect_timing=True,
        )
    except Exception:
        handle.close()
        raise
    return (
        engine,
        d3xx_candidate.candidate.product_string,
        d3xx_candidate.candidate.product_string_status,
    )


@pytest.mark.requires_n3dsxl
def test_n3dsxl_d3xx_native_timing_smoke(tmp_path: Path) -> None:
    if not hardware_approved(os.environ):
        pytest.skip("set PONKAN_HARDWARE_APPROVED=1 after reviewing the hardware command scope")

    engine, product_string, product_string_status = _open_d3xx_native_streaming_engine()
    stats = run_streaming_smoke(
        engine,
        duration=10.0,
        noop_consumer=True,
        product_string=product_string,
        product_string_status=product_string_status,
        backend_kind="d3xx-native",
        driver_service=os.environ.get("PONKAN_N3DSXL_DRIVER_SERVICE", "FTDIBUS3"),
        mode_3d=False,
        raw_slots=2,
        output_queue_size=2,
        drop_policy="drop_oldest",
    )
    stats_path = n3dsxl_artifact_dir("native-timing-smoke", root=tmp_path) / "stream_stats.json"
    write_json_artifact(stats_path, stats.to_dict())

    assert stats.backend_kind == "d3xx-native"
    assert stats.usb_errors == 0
    assert stats.decode_errors == 0
    assert stats.decoded > 0
    assert stats.delivered > 0
    assert stats.shutdown_seconds <= 2.0
    assert stats.timing is not None
    assert "read_duration_ms" in stats.timing
