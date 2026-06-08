"""Streaming counters."""

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(slots=True)
class StreamStats:
    """Mutable streaming counters.

    Attributes:
        submitted: Raw reads submitted to the backend.
        completed: Backend completions received.
        decoded: Raw completions decoded into frames.
        delivered: Decoded frames retained for consumers.
        dropped_raw: Raw completions dropped before decode.
        dropped_decoded: Decoded frames dropped by queue policy.
        usb_errors: Backend completion errors.
        decode_errors: Decoder failures.
        cancelled: In-flight transfers cancelled during shutdown.
        last_error: Optional class name for the last decode error.
    """

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
        """Return a copy suitable for reporting.

        Returns:
            Independent counter object representing the current values.
        """
        return StreamStats(**asdict(self))

    def to_dict(self) -> dict[str, int | str | None]:
        """Return JSON-serializable counters.

        Returns:
            Dictionary form of all stream counters.
        """
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PerformanceStats:
    """JSON-serializable performance smoke report.

    Attributes mirror the performance smoke artifact schema. Time values are
    seconds, and ``delivered_fps`` is calculated from delivered frame count and
    requested duration.
    """

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
        """Build a performance report from streaming counters.

        Args:
            stats: Streaming counters collected during the smoke run.
            product_string: USB product string when readable.
            product_string_status: Whether the product string was accepted or
                unreadable.
            mode_3d: Capture mode used by the smoke run.
            duration_seconds: Requested smoke duration in seconds.
            raw_slots: Raw transfer slot count.
            output_queue_size: Decoded frame queue capacity.
            drop_policy: Decoded frame overflow policy.
            shutdown_seconds: Time spent stopping the engine.
            backend_kind: Transport backend used for the run.
            driver_service: Optional Windows driver service observed.

        Returns:
            Frozen JSON-serializable performance report.
        """
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
        """Return JSON-serializable performance stats.

        Returns:
            Dictionary form suitable for JSON artifact output.
        """
        return asdict(self)
