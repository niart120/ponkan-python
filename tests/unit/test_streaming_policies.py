import numpy as np
import pytest

from ponkan.image.frame import CaptureFrame
from ponkan.streaming.policies import BoundedFrameQueue, put_frame_with_policy
from ponkan.streaming.stats import StreamStats


def _frame(value: int) -> CaptureFrame:
    top = np.full((240, 400, 3), value, dtype=np.uint8)
    bottom = np.full((240, 320, 3), value, dtype=np.uint8)
    return CaptureFrame(
        top=top,
        bottom=bottom,
        top_right=None,
        timestamp_ns=None,
        source_model="new_3ds_xl",
        mode_3d=False,
    )


def test_drop_oldest_discards_oldest_frame() -> None:
    queue = BoundedFrameQueue(1)
    stats = StreamStats()

    put_frame_with_policy(queue, _frame(1), "drop_oldest", stats)
    put_frame_with_policy(queue, _frame(2), "drop_oldest", stats)

    assert queue.get_nowait().top[0, 0, 0] == 2
    assert stats.dropped_decoded == 1
    assert stats.delivered == 2


def test_drop_newest_discards_new_frame() -> None:
    queue = BoundedFrameQueue(1)
    stats = StreamStats()

    put_frame_with_policy(queue, _frame(1), "drop_newest", stats)
    put_frame_with_policy(queue, _frame(2), "drop_newest", stats)

    assert queue.get_nowait().top[0, 0, 0] == 1
    assert stats.dropped_decoded == 1
    assert stats.delivered == 1


def test_block_policy_is_rejected_on_callback_thread() -> None:
    queue = BoundedFrameQueue(1)
    stats = StreamStats()

    put_frame_with_policy(queue, _frame(1), "drop_oldest", stats)
    with pytest.raises(RuntimeError):
        put_frame_with_policy(queue, _frame(2), "block", stats, callback_thread=True)
