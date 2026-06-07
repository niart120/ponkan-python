import os

import pytest

from py3dscapture.streaming.engine import StreamingEngine
from py3dscapture.transport.libusb_async import LibusbAsyncBackend


@pytest.mark.requires_n3dsxl
def test_n3dsxl_streaming_10_second_smoke() -> None:
    if os.environ.get("PONKAN_HARDWARE_APPROVED") != "1":
        pytest.skip("set PONKAN_HARDWARE_APPROVED=1 after reviewing the hardware command scope")

    engine = StreamingEngine(LibusbAsyncBackend())
    engine.start()
    try:
        engine.process_completed(limit=1)
    finally:
        engine.stop()
