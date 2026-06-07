"""Stream N3DSXL frames and print stats."""

import argparse
import json
import time
from pathlib import Path

from py3dscapture.streaming.engine import StreamingEngine
from py3dscapture.transport.libusb_async import LibusbAsyncBackend


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--stats-json", type=Path)
    parser.add_argument("--noop-consumer", action="store_true")
    args = parser.parse_args(argv)

    engine = StreamingEngine(LibusbAsyncBackend())
    started = time.monotonic()
    try:
        engine.start()
        while time.monotonic() - started < args.duration:
            engine.process_completed(limit=8)
            if args.noop_consumer:
                for _frame in engine.frames():
                    pass
            time.sleep(0.01)
    finally:
        engine.stop()

    stats = engine.stats().to_dict()
    if args.stats:
        print(json.dumps(stats, sort_keys=True))
    if args.stats_json is not None:
        args.stats_json.parent.mkdir(parents=True, exist_ok=True)
        args.stats_json.write_text(json.dumps(stats, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
