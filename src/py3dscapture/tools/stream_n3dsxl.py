"""Stream N3DSXL frames and print stats."""

import argparse
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from py3dscapture.artifacts import write_json_artifact
from py3dscapture.streaming.engine import StreamingEngine
from py3dscapture.streaming.stats import PerformanceStats
from py3dscapture.transport.libusb_async import LibusbAsyncBackend

if TYPE_CHECKING:
    from py3dscapture.streaming.policies import DropPolicy


def run_streaming_smoke(
    engine: StreamingEngine,
    *,
    duration: float,
    noop_consumer: bool,
    product_string: str | None,
    product_string_status: Literal["accepted", "unreadable"],
    mode_3d: bool,
    raw_slots: int,
    output_queue_size: int,
    drop_policy: str,
    backend_kind: Literal["libusb", "d3xx"] = "libusb",
    driver_service: str | None = None,
    poll_interval: float = 0.01,
) -> PerformanceStats:
    """Run a bounded streaming smoke loop and return performance stats.

    Args:
        engine: Streaming engine to start, poll, and stop.
        duration: Requested run duration in seconds.
        noop_consumer: Drain decoded frames without inspecting them when true.
        product_string: USB product string recorded for the run.
        product_string_status: Whether the product string was accepted or
            unreadable.
        mode_3d: Capture mode recorded in the report.
        raw_slots: Raw slot count used by the engine.
        output_queue_size: Decoded frame queue capacity used by the engine.
        drop_policy: Decoded-frame overflow policy.
        backend_kind: Transport backend recorded in the report.
        driver_service: Optional Windows driver service recorded in the report.
        poll_interval: Sleep interval between completion polls.

    Returns:
        JSON-serializable performance report.
    """
    started = time.monotonic()
    engine_started = False
    shutdown_seconds = 0.0
    try:
        engine.start()
        engine_started = True
        while time.monotonic() - started < duration:
            engine.process_completed(limit=8)
            if noop_consumer:
                for _frame in engine.frames():
                    pass
            time.sleep(poll_interval)
    finally:
        shutdown_started = time.monotonic()
        if engine_started:
            engine.stop()
        shutdown_seconds = time.monotonic() - shutdown_started

    return PerformanceStats.from_stream_stats(
        engine.stats(),
        product_string=product_string,
        product_string_status=product_string_status,
        backend_kind=backend_kind,
        driver_service=driver_service,
        mode_3d=mode_3d,
        duration_seconds=duration,
        raw_slots=raw_slots,
        output_queue_size=output_queue_size,
        drop_policy=drop_policy,
        shutdown_seconds=shutdown_seconds,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the streaming smoke CLI.

    Args:
        argv: Optional command-line arguments. ``None`` uses ``sys.argv`` through
            ``argparse``.

    Returns:
        Process status code. Zero means the smoke loop completed and requested
        stats output was written.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--stats-json", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--noop-consumer", action="store_true")
    parser.add_argument("--product-string")
    parser.add_argument(
        "--product-string-status",
        choices=("accepted", "unreadable"),
    )
    parser.add_argument("--raw-slots", type=int, default=4)
    parser.add_argument("--output-queue-size", type=int, default=2)
    parser.add_argument(
        "--drop-policy",
        choices=("drop_oldest", "drop_newest", "block"),
        default="drop_oldest",
    )
    args = parser.parse_args(argv)

    drop_policy = cast("DropPolicy", args.drop_policy)
    product_string_status = args.product_string_status or (
        "accepted" if args.product_string is not None else "unreadable"
    )
    engine = StreamingEngine(
        LibusbAsyncBackend(),
        raw_slots=args.raw_slots,
        output_queue_size=args.output_queue_size,
        drop_policy=drop_policy,
    )
    stats = run_streaming_smoke(
        engine,
        duration=args.duration,
        noop_consumer=args.noop_consumer,
        product_string=args.product_string,
        product_string_status=cast("Literal['accepted', 'unreadable']", product_string_status),
        mode_3d=False,
        raw_slots=args.raw_slots,
        output_queue_size=args.output_queue_size,
        drop_policy=args.drop_policy,
    )

    if args.stats:
        print(json.dumps(stats.to_dict(), sort_keys=True))
    if args.stats_json is not None:
        write_json_artifact(args.stats_json, stats.to_dict(), force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
