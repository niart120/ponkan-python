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
from py3dscapture.streaming.stats import StreamStats, StreamTimingCollector, TimingSummary
from py3dscapture.transport.libusb_async import AsyncTransferBackend

Decoder = Callable[[bytes], CaptureFrame]


class StreamingEngine:
    """Coordinate raw async acquisition, decode handoff, and frame delivery.

    Transfer callbacks only enqueue raw completion metadata. Decoding and
    decoded-frame queue policy are handled by ``process_completed`` outside the
    callback path.
    """

    def __init__(
        self,
        backend: AsyncTransferBackend,
        *,
        raw_slots: int = 2,
        raw_slot_size: int | None = None,
        output_queue_size: int = 2,
        drop_policy: DropPolicy = "drop_oldest",
        decoder: Decoder | None = None,
        collect_timing: bool = False,
    ) -> None:
        """Create a streaming engine over an async transfer backend.

        Args:
            backend: Async transfer backend that fills raw slots and invokes a
                completion callback.
            raw_slots: Number of in-flight raw transfer buffers.
            raw_slot_size: Byte size for each raw slot. Defaults to the 2D
                capture size.
            output_queue_size: Number of decoded frames retained for consumers.
            drop_policy: Overflow behavior for decoded-frame delivery.
            decoder: Optional raw-video decoder used for tests or alternate
                decode strategies.
            collect_timing: Collect per-transfer timing samples and expose a
                summary through ``timing_summary`` when true.

        Raises:
            ValueError: Slot or queue sizes are not positive.
        """
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
        self._timing = StreamTimingCollector() if collect_timing else None

    def start(self) -> None:
        """Submit initial raw-slot async reads.

        The method is idempotent while already running. Each slot is checked out
        and submitted once.
        """
        if self._running:
            return
        self._running = True
        for slot in self.buffer_pool.slots:
            self._submit_slot(self.buffer_pool.checkout(slot.index))

    def stop(self, timeout: float | None = None) -> None:
        """Cancel, drain, release backend resources, and release raw slots.

        Args:
            timeout: Reserved for future bounded shutdown support. Current
                shutdown drains using the backend's own semantics.
        """
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
        """Decode completed raw results outside the callback.

        Args:
            limit: Maximum number of completions to process, or ``None`` to
                process until the completion queue is empty.

        Returns:
            Number of raw completions consumed from the completion queue.
        """
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
        """Yield decoded frames currently available to consumers.

        Args:
            max_frames: Maximum number of frames to yield, or ``None`` to drain
                all currently queued frames.

        Yields:
            Decoded frames from the output queue in delivery order.
        """
        delivered = 0
        while max_frames is None or delivered < max_frames:
            try:
                frame = self.output_queue.get_nowait()
            except IndexError:
                break
            delivered += 1
            yield frame

    async def frames_async(self, *, max_frames: int | None = None) -> AsyncIterator[CaptureFrame]:
        """Yield decoded frames through an async iterator.

        Args:
            max_frames: Maximum number of frames to yield, or ``None`` to drain
                all currently queued frames.

        Yields:
            Decoded frames from the output queue in delivery order.
        """
        delivered = 0
        while max_frames is None or delivered < max_frames:
            frame = next(self.frames(max_frames=1), None)
            if frame is None:
                break
            delivered += 1
            yield frame
            await asyncio.sleep(0)

    def stats(self) -> StreamStats:
        """Return a snapshot of current stream counters.

        Returns:
            Independent counter snapshot for reporting.
        """
        return self._stats.snapshot()

    def timing_summary(self) -> TimingSummary | None:
        """Return opt-in timing summary for completed samples.

        Returns:
            Timing summary when collection is enabled, otherwise ``None``.
        """
        if self._timing is None:
            return None
        return self._timing.summary()

    def _submit_slot(self, slot: RawFrameSlot) -> None:
        slot.submitted_ns = time.monotonic_ns()
        slot.backend_started_ns = None
        slot.completed_ns = None
        slot.transferred = 0
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
        submitted_ns = slot.submitted_ns
        backend_started_ns = slot.backend_started_ns
        sequence = 0 if slot.sequence is None else slot.sequence
        result = RawFrameResult(
            slot_index=slot_index,
            view=slot.view,
            transferred=transferred,
            status=status,
            submitted_ns=submitted_ns,
            backend_started_ns=backend_started_ns,
            completed_ns=completed_ns,
            sequence=sequence,
        )
        if self._timing is not None:
            self._timing.record_completion_interval(completed_ns)
            if submitted_ns is not None:
                self._timing.record_ns_delta(
                    "submit_to_complete_ms",
                    completed_ns - submitted_ns,
                )
                if backend_started_ns is not None:
                    self._timing.record_ns_delta(
                        "backend_queue_wait_ms",
                        backend_started_ns - submitted_ns,
                    )
            if backend_started_ns is not None:
                self._timing.record_ns_delta(
                    "read_duration_ms",
                    completed_ns - backend_started_ns,
                )
        try:
            self._completion_queue.put_nowait(result)
        except queue.Full:
            self._stats.dropped_raw += 1
            self.buffer_pool.release(slot_index)
        else:
            self._stats.completed += 1

    def _process_result(self, result: RawFrameResult) -> None:
        if self._timing is not None:
            process_started_ns = time.monotonic_ns()
            self._timing.record_ns_delta(
                "completion_queue_wait_ms",
                process_started_ns - result.completed_ns,
            )
        try:
            if result.status != 0:
                self._stats.usb_errors += 1
                return
            expected_video_size = video_size(mode_3d=False)
            if result.transferred < expected_video_size:
                self._stats.dropped_raw += 1
                return
            raw_video = bytes(result.view[:expected_video_size])
            if self._timing is None:
                frame = self._decoder(raw_video)
            else:
                decode_started_ns = time.monotonic_ns()
                try:
                    frame = self._decoder(raw_video)
                finally:
                    self._timing.record_ns_delta(
                        "decode_ms",
                        time.monotonic_ns() - decode_started_ns,
                    )
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
                if self._timing is not None:
                    resubmit_started_ns = time.monotonic_ns()
                    self._timing.record_ns_delta(
                        "callback_to_resubmit_ms",
                        resubmit_started_ns - result.completed_ns,
                    )
                self._submit_slot(self.buffer_pool.checkout(result.slot_index))


def _decode_2d_default(raw_video: bytes) -> CaptureFrame:
    return decode_rgb8_2d(raw_video)
