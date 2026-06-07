"""Raw streaming buffer pool."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class RawFrameSlot:
    """One reusable raw transfer slot."""

    index: int
    buffer: bytearray
    view: memoryview = field(init=False)
    in_use: bool = False
    submitted_ns: int | None = None
    completed_ns: int | None = None
    transferred: int = 0
    sequence: int | None = None

    def __post_init__(self) -> None:
        """Create a stable memoryview for the slot buffer."""
        self.view = memoryview(self.buffer)


@dataclass(frozen=True, slots=True)
class RawFrameResult:
    """Completed raw transfer metadata."""

    slot_index: int
    view: memoryview
    transferred: int
    status: int
    completed_ns: int
    sequence: int


class BufferPool:
    """Preallocated raw slot pool."""

    def __init__(self, *, raw_slots: int, raw_slot_size: int) -> None:
        """Create fixed raw slots."""
        if raw_slots <= 0 or raw_slot_size <= 0:
            raise ValueError
        self._slots = tuple(
            RawFrameSlot(index=index, buffer=bytearray(raw_slot_size)) for index in range(raw_slots)
        )

    @property
    def slots(self) -> tuple[RawFrameSlot, ...]:
        """Return all slots."""
        return self._slots

    def checkout(self, index: int) -> RawFrameSlot:
        """Mark one slot in use."""
        slot = self._slots[index]
        if slot.in_use:
            raise RuntimeError
        slot.in_use = True
        return slot

    def release(self, index: int) -> None:
        """Release one slot."""
        slot = self._slots[index]
        slot.in_use = False
        slot.submitted_ns = None
        slot.completed_ns = None
        slot.transferred = 0
        slot.sequence = None

    def get(self, index: int) -> RawFrameSlot:
        """Return one slot by index."""
        return self._slots[index]

    def in_use_count(self) -> int:
        """Return the number of checked-out slots."""
        return sum(1 for slot in self._slots if slot.in_use)
