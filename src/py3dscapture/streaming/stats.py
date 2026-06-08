"""Streaming counters."""

from dataclasses import asdict, dataclass, field
from threading import Lock
from typing import Literal

TIMING_METRIC_NAMES = (
    "backend_queue_wait_ms",
    "read_duration_ms",
    "submit_to_complete_ms",
    "completion_interval_ms",
    "completion_queue_wait_ms",
    "decode_ms",
    "callback_to_resubmit_ms",
)

TimingMetricSummary = dict[str, float | int]
TimingSummary = dict[str, TimingMetricSummary]


@dataclass(slots=True)
class StreamTimingCollector:
    """Collect opt-in per-transfer timing samples for streaming reports.

    The collector stores all samples in memory and summarizes them on demand.
    This is intended for bounded smoke runs, not indefinite production
    telemetry.
    """

    _samples: dict[str, list[float]] = field(
        default_factory=lambda: {name: [] for name in TIMING_METRIC_NAMES}
    )
    _last_completed_ns: int | None = None
    _lock: Lock = field(default_factory=Lock)

    def record_ns_delta(self, metric: str, delta_ns: int) -> None:
        """Record one non-negative nanosecond delta as milliseconds.

        Args:
            metric: Metric name from ``TIMING_METRIC_NAMES``.
            delta_ns: Duration in nanoseconds.
        """
        if delta_ns < 0:
            return
        with self._lock:
            self._samples[metric].append(delta_ns / 1_000_000)

    def record_completion_interval(self, completed_ns: int) -> None:
        """Record interval from the previous backend completion.

        Args:
            completed_ns: Monotonic timestamp for the current completion.
        """
        with self._lock:
            if self._last_completed_ns is not None:
                delta_ns = completed_ns - self._last_completed_ns
                if delta_ns >= 0:
                    self._samples["completion_interval_ms"].append(delta_ns / 1_000_000)
            self._last_completed_ns = completed_ns

    def summary(self) -> TimingSummary:
        """Return count/min/percentile/max/mean summaries by metric.

        Returns:
            JSON-serializable timing summary. Metrics without samples are
            omitted.
        """
        with self._lock:
            samples = {name: tuple(values) for name, values in self._samples.items()}
        return {name: _summarize_metric(values) for name, values in samples.items() if values}


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
    timing: TimingSummary | None = None

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
        timing: TimingSummary | None = None,
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
            timing: Optional timing summary collected by ``StreamingEngine``.

        Returns:
            Frozen JSON-serializable performance report.
        """
        delivered_fps = stats.delivered / duration_seconds if duration_seconds > 0 else 0.0
        timing_copy = (
            {metric: dict(summary) for metric, summary in timing.items()}
            if timing is not None
            else None
        )
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
            timing=timing_copy,
        )

    def to_dict(self) -> dict[str, object]:
        """Return JSON-serializable performance stats.

        Returns:
            Dictionary form suitable for JSON artifact output.
        """
        payload = asdict(self)
        if self.timing is None:
            payload.pop("timing")
        return payload


def _summarize_metric(values: tuple[float, ...]) -> TimingMetricSummary:
    ordered = tuple(sorted(values))
    count = len(ordered)
    return {
        "count": count,
        "min": ordered[0],
        "p50": _percentile(ordered, 0.50),
        "p95": _percentile(ordered, 0.95),
        "p99": _percentile(ordered, 0.99),
        "max": ordered[-1],
        "mean": sum(ordered) / count,
    }


def _percentile(values: tuple[float, ...], percentile: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * percentile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(values) - 1)
    fraction = position - lower_index
    return values[lower_index] + (values[upper_index] - values[lower_index]) * fraction
