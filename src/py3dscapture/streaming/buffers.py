"""Raw streaming buffer pool."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class RawFrameSlot:
    """One reusable raw transfer slot.

    Attributes:
        index: Stable slot index used by backend callbacks.
        buffer: Mutable byte storage owned by the pool.
        view: Stable memoryview over ``buffer`` for zero-copy backend writes.
        in_use: Whether the slot is checked out by an in-flight transfer.
        submitted_ns: Optional monotonic timestamp when the transfer was queued.
        backend_started_ns: Optional monotonic timestamp when the backend worker
            started the actual read.
        completed_ns: Optional monotonic timestamp when the transfer completed.
        transferred: Bytes reported by the backend.
        sequence: Optional streaming sequence assigned at submission time.
    """

    index: int
    buffer: bytearray
    view: memoryview = field(init=False)
    in_use: bool = False
    submitted_ns: int | None = None
    backend_started_ns: int | None = None
    completed_ns: int | None = None
    transferred: int = 0
    sequence: int | None = None

    def __post_init__(self) -> None:
        """Create a stable memoryview for the slot buffer.

        The view is reused for the lifetime of the slot so callbacks can refer
        to the same memory without allocating a new memoryview per transfer.
        """
        self.view = memoryview(self.buffer)


@dataclass(frozen=True, slots=True)
class RawFrameResult:
    """Completed raw transfer metadata.

    Attributes:
        slot_index: Slot that produced this result.
        view: Memoryview containing the completed raw bytes.
        transferred: Number of bytes reported by the backend.
        status: Backend completion status, where zero means success.
        submitted_ns: Monotonic submission timestamp when available.
        backend_started_ns: Monotonic backend read-start timestamp when
            available.
        completed_ns: Monotonic completion timestamp.
        sequence: Streaming sequence assigned when the read was submitted.
    """

    slot_index: int
    view: memoryview
    transferred: int
    status: int
    submitted_ns: int | None
    backend_started_ns: int | None
    completed_ns: int
    sequence: int


class BufferPool:
    """Preallocated raw slot pool.

    The pool keeps raw buffers stable so async backends can write into memory
    owned by the streaming engine without allocating per transfer.
    """

    def __init__(self, *, raw_slots: int, raw_slot_size: int) -> None:
        """Create fixed raw slots.

        Args:
            raw_slots: Number of reusable slots to allocate.
            raw_slot_size: Byte size for each raw transfer buffer.

        Raises:
            ValueError: Either value is not positive.
        """
        if raw_slots <= 0 or raw_slot_size <= 0:
            raise ValueError
        self._slots = tuple(
            RawFrameSlot(index=index, buffer=bytearray(raw_slot_size)) for index in range(raw_slots)
        )

    @property
    def slots(self) -> tuple[RawFrameSlot, ...]:
        """Return all slots.

        Returns:
            Tuple of pool slots in stable index order.
        """
        return self._slots

    def checkout(self, index: int) -> RawFrameSlot:
        """Mark one slot in use.

        Args:
            index: Slot index to reserve.

        Returns:
            The reserved slot.

        Raises:
            RuntimeError: The slot is already checked out.
            IndexError: ``index`` is outside the pool.
        """
        slot = self._slots[index]
        if slot.in_use:
            raise RuntimeError
        slot.in_use = True
        return slot

    def release(self, index: int) -> None:
        """Release one slot.

        Args:
            index: Slot index to release and reset.

        Raises:
            IndexError: ``index`` is outside the pool.
        """
        slot = self._slots[index]
        slot.in_use = False
        slot.submitted_ns = None
        slot.backend_started_ns = None
        slot.completed_ns = None
        slot.transferred = 0
        slot.sequence = None

    def get(self, index: int) -> RawFrameSlot:
        """Return one slot by index.

        Args:
            index: Slot index to return.

        Returns:
            The slot with the requested index.

        Raises:
            IndexError: ``index`` is outside the pool.
        """
        return self._slots[index]

    def in_use_count(self) -> int:
        """Return the number of checked-out slots.

        Returns:
            Count of slots currently marked in use.
        """
        return sum(1 for slot in self._slots if slot.in_use)
