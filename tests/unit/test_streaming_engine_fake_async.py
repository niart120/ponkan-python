import asyncio
import time

import numpy as np

from py3dscapture.image.frame import CaptureFrame
from py3dscapture.protocol.sizes import BOTTOM_WIDTH_3DS, HEIGHT_3DS, TOP_WIDTH_3DS, video_size
from py3dscapture.streaming.buffers import RawFrameSlot
from py3dscapture.streaming.engine import StreamingEngine
from py3dscapture.transport.libusb_async import AsyncTransferCallback


class _FakeAsyncBackend:
    def __init__(self) -> None:
        self.submitted: list[tuple[int, int, AsyncTransferCallback]] = []
        self.calls: list[str] = []

    def submit_read(
        self,
        slot: RawFrameSlot,
        *,
        length: int,
        callback: AsyncTransferCallback,
    ) -> None:
        self.calls.append("submit")
        self.submitted.append((slot.index, length, callback))

    def complete(self, submit_index: int, payload: bytes, *, status: int = 0) -> None:
        slot_index, _length, callback = self.submitted[submit_index]
        slot = self._slot_lookup[slot_index]
        slot.buffer[: len(payload)] = payload
        callback(slot_index, len(payload), status, time.monotonic_ns())

    def bind_slots(self, slots: tuple[RawFrameSlot, ...]) -> None:
        self._slot_lookup = {slot.index: slot for slot in slots}

    def cancel_all(self) -> None:
        self.calls.append("cancel_all")

    def drain(self) -> None:
        self.calls.append("drain")

    def release(self) -> None:
        self.calls.append("release")


class _DecoderSpy:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, raw_video: bytes) -> CaptureFrame:
        self.calls += 1
        assert len(raw_video) == video_size(False)
        top = np.zeros((240, 400, 3), dtype=np.uint8)
        bottom = np.zeros((240, 320, 3), dtype=np.uint8)
        top[:, :, 0] = self.calls
        return CaptureFrame(
            top=top,
            bottom=bottom,
            top_right=None,
            timestamp_ns=None,
            source_model="new_3ds_xl",
            mode_3d=False,
        )


def _raw_payload(value: int = 1) -> bytes:
    return bytes([value]) * video_size(False)


def _ftd3_raw_payload() -> bytes:
    width_delta = TOP_WIDTH_3DS - BOTTOM_WIDTH_3DS
    stacked = np.zeros((TOP_WIDTH_3DS + BOTTOM_WIDTH_3DS, HEIGHT_3DS, 3), dtype=np.uint8)
    stacked[:width_delta] = [10, 11, 12]
    stacked[width_delta::2] = [4, 5, 6]
    stacked[width_delta + 1 :: 2] = [1, 2, 3]
    return stacked.tobytes()


def test_start_submits_raw_slots() -> None:
    backend = _FakeAsyncBackend()
    engine = StreamingEngine(backend, raw_slots=4, raw_slot_size=video_size(False))
    backend.bind_slots(engine.buffer_pool.slots)

    engine.start()

    assert len(backend.submitted) == 4
    assert engine.stats().submitted == 4


def test_callback_does_not_decode_until_processed() -> None:
    backend = _FakeAsyncBackend()
    decoder = _DecoderSpy()
    engine = StreamingEngine(
        backend,
        raw_slots=1,
        raw_slot_size=video_size(False),
        decoder=decoder,
    )
    backend.bind_slots(engine.buffer_pool.slots)
    engine.start()

    backend.complete(0, _raw_payload())

    assert decoder.calls == 0
    assert engine.stats().completed == 1
    engine.process_completed(limit=1)
    assert decoder.calls == 1
    assert engine.stats().decoded == 1


def test_short_transfer_is_not_decoded() -> None:
    backend = _FakeAsyncBackend()
    decoder = _DecoderSpy()
    engine = StreamingEngine(
        backend,
        raw_slots=1,
        raw_slot_size=video_size(False),
        decoder=decoder,
    )
    backend.bind_slots(engine.buffer_pool.slots)
    engine.start()

    backend.complete(0, b"x" * (video_size(False) - 1))
    engine.process_completed(limit=1)

    assert decoder.calls == 0
    assert engine.stats().decoded == 0
    assert engine.stats().dropped_raw == 1
    assert len(backend.submitted) == 2


def test_frames_iterator_delivers_decoded_frame() -> None:
    backend = _FakeAsyncBackend()
    engine = StreamingEngine(backend, raw_slots=1, raw_slot_size=video_size(False))
    backend.bind_slots(engine.buffer_pool.slots)
    engine.start()
    backend.complete(0, _raw_payload())
    engine.process_completed(limit=1)

    frames = list(engine.frames(max_frames=1))

    assert len(frames) == 1
    assert frames[0].sequence == 0


def test_default_decoder_uses_ftd3_cc3dsfs_layout() -> None:
    backend = _FakeAsyncBackend()
    engine = StreamingEngine(backend, raw_slots=1, raw_slot_size=video_size(False))
    backend.bind_slots(engine.buffer_pool.slots)
    engine.start()
    backend.complete(0, _ftd3_raw_payload())
    engine.process_completed(limit=1)

    frame = next(engine.frames(max_frames=1))

    assert {tuple(pixel) for pixel in frame.top.reshape(-1, 3)} == {
        (1, 2, 3),
        (10, 11, 12),
    }
    assert np.all(frame.bottom == [4, 5, 6])


def test_frames_async_delivers_decoded_frame() -> None:
    backend = _FakeAsyncBackend()
    engine = StreamingEngine(backend, raw_slots=1, raw_slot_size=video_size(False))
    backend.bind_slots(engine.buffer_pool.slots)
    engine.start()
    backend.complete(0, _raw_payload())
    engine.process_completed(limit=1)

    async def collect() -> list[CaptureFrame]:
        return [frame async for frame in engine.frames_async(max_frames=1)]

    frames = asyncio.run(collect())
    assert len(frames) == 1


def test_stop_uses_cancel_drain_release_order() -> None:
    backend = _FakeAsyncBackend()
    engine = StreamingEngine(backend, raw_slots=2, raw_slot_size=video_size(False))
    backend.bind_slots(engine.buffer_pool.slots)
    engine.start()

    engine.stop()

    assert backend.calls[-3:] == ["cancel_all", "drain", "release"]
    assert engine.buffer_pool.in_use_count() == 0
    assert engine.stats().cancelled == 2
