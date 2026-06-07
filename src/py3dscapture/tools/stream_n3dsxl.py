"""Stream N3DSXL frames and print stats."""

import argparse
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

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
    product_string: str,
    mode_3d: bool,
    raw_slots: int,
    output_queue_size: int,
    drop_policy: str,
    poll_interval: float = 0.01,
) -> PerformanceStats:
    """Run a bounded streaming smoke loop and return performance stats."""
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
        mode_3d=mode_3d,
        duration_seconds=duration,
        raw_slots=raw_slots,
        output_queue_size=output_queue_size,
        drop_policy=drop_policy,
        shutdown_seconds=shutdown_seconds,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--stats-json", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--noop-consumer", action="store_true")
    parser.add_argument("--product-string", default="unknown")
    parser.add_argument("--raw-slots", type=int, default=4)
    parser.add_argument("--output-queue-size", type=int, default=2)
    parser.add_argument(
        "--drop-policy",
        choices=("drop_oldest", "drop_newest", "block"),
        default="drop_oldest",
    )
    args = parser.parse_args(argv)

    drop_policy = cast("DropPolicy", args.drop_policy)
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
