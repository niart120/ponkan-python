from ponkan.streaming.buffers import BufferPool


def test_raw_frame_slot_has_capture_sized_buffer() -> None:
    pool = BufferPool(raw_slots=1, raw_slot_size=16)

    slot = pool.slots[0]

    assert len(slot.buffer) == 16
    assert len(slot.view) == 16
    assert slot.in_use is False


def test_buffer_pool_preallocates_raw_slots() -> None:
    pool = BufferPool(raw_slots=4, raw_slot_size=8)

    assert len(pool.slots) == 4
    assert {id(slot.buffer) for slot in pool.slots} == {id(slot.buffer) for slot in pool.slots}


def test_checked_out_slot_cannot_be_checked_out_twice() -> None:
    pool = BufferPool(raw_slots=1, raw_slot_size=8)

    slot = pool.checkout(0)

    assert slot.in_use is True
    try:
        pool.checkout(0)
    except RuntimeError:
        pass
    else:  # pragma: no cover
        raise AssertionError
    pool.release(0)
    assert slot.in_use is False
