import os
from typing import TYPE_CHECKING, Literal, cast

import pytest

from py3dscapture.hardware_gate import hardware_approved
from py3dscapture.protocol.n3dsxl import N3DSXLProtocol
from py3dscapture.streaming.engine import StreamingEngine
from py3dscapture.tools.stream_n3dsxl import run_streaming_smoke
from py3dscapture.transport.d3xx_backend import D3xxBackend
from py3dscapture.transport.d3xx_streaming import D3xxAsyncBackend

if TYPE_CHECKING:
    from py3dscapture.protocol.n3dsxl import N3DSXLPipe


def _open_d3xx_streaming_engine() -> tuple[
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
    except Exception:
        handle.close()
        raise
    engine = StreamingEngine(
        D3xxAsyncBackend(handle),
        raw_slots=2,
        output_queue_size=2,
        drop_policy="drop_oldest",
    )
    return (
        engine,
        d3xx_candidate.candidate.product_string,
        d3xx_candidate.candidate.product_string_status,
    )


@pytest.mark.requires_n3dsxl
def test_n3dsxl_d3xx_streaming_smoke() -> None:
    if not hardware_approved(os.environ):
        pytest.skip("set PONKAN_HARDWARE_APPROVED=1 after reviewing the hardware command scope")

    engine, product_string, product_string_status = _open_d3xx_streaming_engine()
    stats = run_streaming_smoke(
        engine,
        duration=2.0,
        noop_consumer=True,
        product_string=product_string,
        product_string_status=product_string_status,
        backend_kind="d3xx",
        driver_service=os.environ.get("PONKAN_N3DSXL_DRIVER_SERVICE", "FTDIBUS3"),
        mode_3d=False,
        raw_slots=2,
        output_queue_size=2,
        drop_policy="drop_oldest",
    )

    assert stats.backend_kind == "d3xx"
    assert stats.usb_errors == 0
    assert stats.decode_errors == 0
    assert stats.decoded > 0
    assert stats.delivered > 0
    assert stats.shutdown_seconds <= 2.0
