"""Streaming counters."""

from dataclasses import asdict, dataclass
from typing import Literal


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


@dataclass(frozen=True, slots=True)
class PerformanceStats:
    """JSON-serializable performance smoke report."""

    model: Literal["new_3ds_xl"]
    product_string: str | None
    product_string_status: Literal["accepted", "unreadable"]
    backend_kind: Literal["libusb", "d3xx"]
    driver_service: str | None
    mode_3d: bool
    duration_seconds: float
    raw_slots: int
    output_queue_size: int
    drop_policy: str
    submitted: int
    completed: int
    decoded: int
    delivered: int
    dropped_raw: int
    dropped_decoded: int
    usb_errors: int
    decode_errors: int
    cancelled: int
    last_error: str | None
    shutdown_seconds: float
    delivered_fps: float

    @classmethod
    def from_stream_stats(
        cls,
        stats: StreamStats,
        *,
        product_string: str | None,
        product_string_status: Literal["accepted", "unreadable"],
        mode_3d: bool,
        duration_seconds: float,
        raw_slots: int,
        output_queue_size: int,
        drop_policy: str,
        shutdown_seconds: float,
        backend_kind: Literal["libusb", "d3xx"] = "libusb",
        driver_service: str | None = None,
    ) -> "PerformanceStats":
        """Build a performance report from streaming counters."""
        delivered_fps = stats.delivered / duration_seconds if duration_seconds > 0 else 0.0
        return cls(
            model="new_3ds_xl",
            product_string=product_string,
            product_string_status=product_string_status,
            backend_kind=backend_kind,
            driver_service=driver_service,
            mode_3d=mode_3d,
            duration_seconds=duration_seconds,
            raw_slots=raw_slots,
            output_queue_size=output_queue_size,
            drop_policy=drop_policy,
            submitted=stats.submitted,
            completed=stats.completed,
            decoded=stats.decoded,
            delivered=stats.delivered,
            dropped_raw=stats.dropped_raw,
            dropped_decoded=stats.dropped_decoded,
            usb_errors=stats.usb_errors,
            decode_errors=stats.decode_errors,
            cancelled=stats.cancelled,
            last_error=stats.last_error,
            shutdown_seconds=shutdown_seconds,
            delivered_fps=delivered_fps,
        )

    def to_dict(self) -> dict[str, bool | float | int | str | None]:
        """Return JSON-serializable performance stats."""
        return asdict(self)
