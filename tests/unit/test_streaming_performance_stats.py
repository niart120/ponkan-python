from py3dscapture.streaming.stats import PerformanceStats, StreamStats


def test_performance_stats_include_smoke_gate_fields() -> None:
    counters = StreamStats(
        submitted=120,
        completed=118,
        decoded=117,
        delivered=90,
        dropped_raw=1,
        dropped_decoded=2,
        usb_errors=0,
        decode_errors=3,
        cancelled=4,
        last_error="DecodeError",
    )

    stats = PerformanceStats.from_stream_stats(
        counters,
        product_string="N3DSXL",
        product_string_status="accepted",
        mode_3d=False,
        duration_seconds=3.0,
        raw_slots=4,
        output_queue_size=2,
        drop_policy="drop_oldest",
        shutdown_seconds=0.25,
        backend_kind="d3xx",
        driver_service="FTDIBUS3",
    )

    assert stats.to_dict() == {
        "model": "new_3ds_xl",
        "product_string": "N3DSXL",
        "product_string_status": "accepted",
        "backend_kind": "d3xx",
        "driver_service": "FTDIBUS3",
        "mode_3d": False,
        "duration_seconds": 3.0,
        "raw_slots": 4,
        "output_queue_size": 2,
        "drop_policy": "drop_oldest",
        "submitted": 120,
        "completed": 118,
        "decoded": 117,
        "delivered": 90,
        "dropped_raw": 1,
        "dropped_decoded": 2,
        "usb_errors": 0,
        "decode_errors": 3,
        "cancelled": 4,
        "last_error": "DecodeError",
        "shutdown_seconds": 0.25,
        "delivered_fps": 30.0,
    }


def test_performance_stats_zero_duration_reports_zero_fps() -> None:
    stats = PerformanceStats.from_stream_stats(
        StreamStats(delivered=1),
        product_string=None,
        product_string_status="unreadable",
        mode_3d=False,
        duration_seconds=0.0,
        raw_slots=4,
        output_queue_size=2,
        drop_policy="drop_oldest",
        shutdown_seconds=0.0,
        backend_kind="libusb",
        driver_service=None,
    )

    assert stats.delivered_fps == 0.0


def test_performance_stats_include_timing_when_supplied() -> None:
    stats = PerformanceStats.from_stream_stats(
        StreamStats(delivered=1),
        product_string=None,
        product_string_status="unreadable",
        mode_3d=False,
        duration_seconds=1.0,
        raw_slots=4,
        output_queue_size=2,
        drop_policy="drop_oldest",
        shutdown_seconds=0.0,
        backend_kind="d3xx",
        driver_service="FTDIBUS3",
        timing={
            "read_duration_ms": {
                "count": 1,
                "min": 2.0,
                "p50": 2.0,
                "p95": 2.0,
                "p99": 2.0,
                "max": 2.0,
                "mean": 2.0,
            }
        },
    )

    assert stats.to_dict()["timing"] == {
        "read_duration_ms": {
            "count": 1,
            "min": 2.0,
            "p50": 2.0,
            "p95": 2.0,
            "p99": 2.0,
            "max": 2.0,
            "mean": 2.0,
        }
    }
