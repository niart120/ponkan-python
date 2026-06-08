"""Streaming engine built around async raw completions."""

import asyncio
import queue
import time
from collections.abc import AsyncIterator, Callable, Iterator

from py3dscapture.errors import DecodeError
from py3dscapture.image.frame import CaptureFrame
from py3dscapture.protocol.layout_3ds import decode_rgb8_2d
from py3dscapture.protocol.sizes import capture_size, video_size
from py3dscapture.streaming.buffers import BufferPool, RawFrameResult, RawFrameSlot
from py3dscapture.streaming.policies import BoundedFrameQueue, DropPolicy, put_frame_with_policy
from py3dscapture.streaming.stats import StreamStats
from py3dscapture.transport.libusb_async import AsyncTransferBackend

Decoder = Callable[[bytes], CaptureFrame]


class StreamingEngine:
    """Coordinate raw async acquisition, decode handoff, and frame delivery."""

    def __init__(
        self,
        backend: AsyncTransferBackend,
        *,
        raw_slots: int = 4,
        raw_slot_size: int | None = None,
        output_queue_size: int = 2,
        drop_policy: DropPolicy = "drop_oldest",
        decoder: Decoder | None = None,
    ) -> None:
        """Create a streaming engine over an async transfer backend."""
        self.raw_slot_size = raw_slot_size or capture_size(mode_3d=False)
        self.buffer_pool = BufferPool(raw_slots=raw_slots, raw_slot_size=self.raw_slot_size)
        self.backend = backend
        self.output_queue = BoundedFrameQueue(output_queue_size)
        self.drop_policy = drop_policy
        self._decoder = decoder or _decode_2d_default
        self._stats = StreamStats()
        self._completion_queue: queue.Queue[RawFrameResult] = queue.Queue(maxsize=raw_slots)
        self._running = False
        self._next_sequence = 0

    def start(self) -> None:
        """Submit initial raw_slots async reads."""
        if self._running:
            return
        self._running = True
        for slot in self.buffer_pool.slots:
            self._submit_slot(self.buffer_pool.checkout(slot.index))

    def stop(self, timeout: float | None = None) -> None:
        """Cancel, drain, release backend resources, and release raw slots."""
        _ = timeout
        if not self._running and self.buffer_pool.in_use_count() == 0:
            return
        self._running = False
        self._stats.cancelled += self.buffer_pool.in_use_count()
        self.backend.cancel_all()
        self.backend.drain()
        for slot in self.buffer_pool.slots:
            if slot.in_use:
                self.buffer_pool.release(slot.index)
        self.backend.release()

    def process_completed(self, *, limit: int | None = None) -> int:
        """Decode completed raw results outside the callback."""
        processed = 0
        while limit is None or processed < limit:
            try:
                result = self._completion_queue.get_nowait()
            except queue.Empty:
                break
            processed += 1
            self._process_result(result)
        return processed

    def frames(self, *, max_frames: int | None = None) -> Iterator[CaptureFrame]:
        """Yield decoded frames currently available to consumers."""
        delivered = 0
        while max_frames is None or delivered < max_frames:
            try:
                frame = self.output_queue.get_nowait()
            except IndexError:
                break
            delivered += 1
            yield frame

    async def frames_async(self, *, max_frames: int | None = None) -> AsyncIterator[CaptureFrame]:
        """Yield decoded frames through an async iterator."""
        delivered = 0
        while max_frames is None or delivered < max_frames:
            frame = next(self.frames(max_frames=1), None)
            if frame is None:
                break
            delivered += 1
            yield frame
            await asyncio.sleep(0)

    def stats(self) -> StreamStats:
        """Return a snapshot of current stream counters."""
        return self._stats.snapshot()

    def _submit_slot(self, slot: RawFrameSlot) -> None:
        slot.submitted_ns = time.monotonic_ns()
        slot.sequence = self._next_sequence
        self._next_sequence += 1
        self.backend.submit_read(
            slot,
            length=self.raw_slot_size,
            callback=self._on_transfer_complete,
        )
        self._stats.submitted += 1

    def _on_transfer_complete(
        self,
        slot_index: int,
        transferred: int,
        status: int,
        completed_ns: int,
    ) -> None:
        slot = self.buffer_pool.get(slot_index)
        slot.completed_ns = completed_ns
        slot.transferred = transferred
        sequence = 0 if slot.sequence is None else slot.sequence
        result = RawFrameResult(
            slot_index=slot_index,
            view=slot.view,
            transferred=transferred,
            status=status,
            completed_ns=completed_ns,
            sequence=sequence,
        )
        try:
            self._completion_queue.put_nowait(result)
        except queue.Full:
            self._stats.dropped_raw += 1
            self.buffer_pool.release(slot_index)
        else:
            self._stats.completed += 1

    def _process_result(self, result: RawFrameResult) -> None:
        try:
            if result.status != 0:
                self._stats.usb_errors += 1
                return
            expected_video_size = video_size(mode_3d=False)
            if result.transferred < expected_video_size:
                self._stats.dropped_raw += 1
                return
            raw_video = bytes(result.view[:expected_video_size])
            frame = self._decoder(raw_video)
            frame.sequence = result.sequence
            frame.timestamp_ns = result.completed_ns
            self._stats.decoded += 1
            put_frame_with_policy(self.output_queue, frame, self.drop_policy, self._stats)
        except DecodeError as exc:
            self._stats.decode_errors += 1
            self._stats.last_error = exc.__class__.__name__
        finally:
            self.buffer_pool.release(result.slot_index)
            if self._running:
                self._submit_slot(self.buffer_pool.checkout(result.slot_index))


def _decode_2d_default(raw_video: bytes) -> CaptureFrame:
    return decode_rgb8_2d(raw_video)
