"""Streaming counters."""

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class StreamStats:
    """Mutable streaming counters."""

    submitted: int = 0
    completed: int = 0
    decoded: int = 0
    delivered: int = 0
    dropped_raw: int = 0
    dropped_decoded: int = 0
    usb_errors: int = 0
    decode_errors: int = 0
    cancelled: int = 0
    last_error: str | None = None

    def snapshot(self) -> "StreamStats":
        """Return a copy suitable for reporting."""
        return StreamStats(**asdict(self))

    def to_dict(self) -> dict[str, int | str | None]:
        """Return JSON-serializable counters."""
        return asdict(self)
