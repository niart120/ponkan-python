import json
from pathlib import Path

import pytest

from ponkan.streaming.stats import StreamStats
from ponkan.tools import stream_n3dsxl


class _FakeBackend:
    pass


class _FakeEngine:
    def __init__(
        self,
        backend: _FakeBackend,
        *,
        raw_slots: int,
        output_queue_size: int,
        drop_policy: str,
        collect_timing: bool = False,
    ) -> None:
        self.backend = backend
        self.raw_slots = raw_slots
        self.output_queue_size = output_queue_size
        self.drop_policy = drop_policy
        self.collect_timing = collect_timing
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def process_completed(self, *, limit: int | None = None) -> int:
        _ = limit
        return 0

    def frames(self) -> tuple[object, ...]:
        return ()

    def stop(self) -> None:
        self.stopped = True

    def stats(self) -> StreamStats:
        return StreamStats(submitted=4, completed=4, decoded=4, delivered=4)

    def timing_summary(self) -> dict[str, dict[str, float | int]] | None:
        if not self.collect_timing:
            return None
        return {
            "read_duration_ms": {
                "count": 1,
                "min": 1.0,
                "p50": 1.0,
                "p95": 1.0,
                "p99": 1.0,
                "max": 1.0,
                "mean": 1.0,
            }
        }


def test_stream_cli_writes_performance_stats_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    stats_path = tmp_path / "artifacts" / "n3dsxl" / "run" / "stream_stats.json"
    monkeypatch.setattr(stream_n3dsxl, "LibusbAsyncBackend", _FakeBackend)
    monkeypatch.setattr(stream_n3dsxl, "StreamingEngine", _FakeEngine)

    exit_code = stream_n3dsxl.main(
        [
            "--duration",
            "0",
            "--noop-consumer",
            "--stats-json",
            str(stats_path),
            "--product-string",
            "N3DSXL",
        ]
    )

    assert exit_code == 0
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    assert stats.pop("shutdown_seconds") >= 0.0
    assert stats == {
        "model": "new_3ds_xl",
        "product_string": "N3DSXL",
        "product_string_status": "accepted",
        "backend_kind": "libusb",
        "driver_service": None,
        "mode_3d": False,
        "duration_seconds": 0.0,
        "raw_slots": 2,
        "output_queue_size": 2,
        "drop_policy": "drop_oldest",
        "submitted": 4,
        "completed": 4,
        "decoded": 4,
        "delivered": 4,
        "dropped_raw": 0,
        "dropped_decoded": 0,
        "usb_errors": 0,
        "decode_errors": 0,
        "cancelled": 0,
        "last_error": None,
        "delivered_fps": 0.0,
    }


def test_stream_cli_writes_timing_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    stats_path = tmp_path / "artifacts" / "n3dsxl" / "run" / "stream_stats.json"
    monkeypatch.setattr(stream_n3dsxl, "LibusbAsyncBackend", _FakeBackend)
    monkeypatch.setattr(stream_n3dsxl, "StreamingEngine", _FakeEngine)

    exit_code = stream_n3dsxl.main(
        [
            "--duration",
            "0",
            "--collect-timing",
            "--stats-json",
            str(stats_path),
        ]
    )

    assert exit_code == 0
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    assert stats["timing"]["read_duration_ms"]["mean"] == 1.0
