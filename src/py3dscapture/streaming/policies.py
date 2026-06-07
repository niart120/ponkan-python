"""Bounded frame delivery queues and drop policies."""

from collections import deque
from collections.abc import Iterator
from typing import Literal

from py3dscapture.image.frame import CaptureFrame
from py3dscapture.streaming.stats import StreamStats

DropPolicy = Literal["drop_oldest", "drop_newest", "block"]
CopyPolicy = Literal["copy_decoded_frame_before_release_raw_slot", "zero_copy_experimental"]


class BoundedFrameQueue:
    """Small FIFO queue for decoded frames."""

    def __init__(self, max_size: int) -> None:
        """Create a bounded queue."""
        if max_size <= 0:
            raise ValueError
        self._max_size = max_size
        self._items: deque[CaptureFrame] = deque()

    @property
    def max_size(self) -> int:
        """Return the queue capacity."""
        return self._max_size

    def __len__(self) -> int:
        """Return queued frame count."""
        return len(self._items)

    def __iter__(self) -> Iterator[CaptureFrame]:
        """Iterate queued frames from oldest to newest."""
        return iter(tuple(self._items))

    def full(self) -> bool:
        """Return whether no more frames can be enqueued."""
        return len(self._items) >= self._max_size

    def put_nowait(self, frame: CaptureFrame) -> None:
        """Append a frame if capacity remains."""
        if self.full():
            raise OverflowError
        self._items.append(frame)

    def put_blocking(self, frame: CaptureFrame) -> None:
        """Append a frame for non-callback contexts."""
        self._items.append(frame)

    def get_nowait(self) -> CaptureFrame:
        """Pop the oldest frame."""
        return self._items.popleft()

    def drop_oldest(self) -> CaptureFrame:
        """Drop and return the oldest frame."""
        return self._items.popleft()


def put_frame_with_policy(
    queue: BoundedFrameQueue,
    frame: CaptureFrame,
    policy: DropPolicy,
    stats: StreamStats,
    *,
    callback_thread: bool = False,
) -> bool:
    """Put one decoded frame using a bounded-queue policy."""
    if policy == "block" and callback_thread:
        raise RuntimeError

    if not queue.full():
        queue.put_nowait(frame)
        stats.delivered += 1
        return True

    if policy == "drop_newest":
        stats.dropped_decoded += 1
        return False
    if policy == "drop_oldest":
        queue.drop_oldest()
        stats.dropped_decoded += 1
        queue.put_nowait(frame)
        stats.delivered += 1
        return True
    if policy == "block":
        queue.put_blocking(frame)
        stats.delivered += 1
        return True
    raise ValueError
