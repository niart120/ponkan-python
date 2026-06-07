from py3dscapture.hardware_gate import (
    HardwareCommandPlan,
    hardware_approved,
    performance_tests_enabled,
    requires_n3dsxl_tests_enabled,
)


def test_hardware_env_flags_require_exact_one() -> None:
    assert not requires_n3dsxl_tests_enabled({})
    assert not requires_n3dsxl_tests_enabled({"PONKAN_RUN_N3DSXL": "true"})
    assert requires_n3dsxl_tests_enabled({"PONKAN_RUN_N3DSXL": "1"})

    assert not performance_tests_enabled({})
    assert not performance_tests_enabled({"PONKAN_RUN_PERFORMANCE": "yes"})
    assert performance_tests_enabled({"PONKAN_RUN_PERFORMANCE": "1"})

    assert not hardware_approved({})
    assert not hardware_approved({"PONKAN_HARDWARE_APPROVED": "yes"})
    assert hardware_approved({"PONKAN_HARDWARE_APPROVED": "1"})


def test_hardware_command_plan_records_safety_boundary() -> None:
    plan = HardwareCommandPlan(
        product_string="N3DSXL",
        product_string_status="accepted",
        vid=0x0403,
        pid=0x601E,
        command_scope="performance",
        safety_reason="requires_n3dsxl marker and explicit hardware approval",
        artifact="artifacts/n3dsxl/20260607T120000/stream_stats.json",
        cleanup="cancel, drain, release, close",
        command='uv run pytest -m "requires_n3dsxl and performance" tests/performance',
        backend_kind="d3xx",
        driver_service="FTDIBUS3",
    )

    assert plan.is_allowed_n3dsxl_device()
    assert plan.to_dict() == {
        "product_string": "N3DSXL",
        "product_string_status": "accepted",
        "vid": "0x0403",
        "pid": "0x601e",
        "command_scope": "performance",
        "safety_reason": "requires_n3dsxl marker and explicit hardware approval",
        "artifact": "artifacts/n3dsxl/20260607T120000/stream_stats.json",
        "cleanup": "cancel, drain, release, close",
        "command": 'uv run pytest -m "requires_n3dsxl and performance" tests/performance',
        "backend_kind": "d3xx",
        "driver_service": "FTDIBUS3",
    }


def test_hardware_command_plan_rejects_non_n3dsxl_identity() -> None:
    plan = HardwareCommandPlan(
        product_string="OLD3DS",
        product_string_status="accepted",
        vid=0x0403,
        pid=0x601E,
        command_scope="performance",
        safety_reason="wrong product string",
        artifact="artifacts/n3dsxl/run/stream_stats.json",
        cleanup="cancel, drain, release, close",
        command="uv run pytest tests/performance",
    )

    assert not plan.is_allowed_n3dsxl_device()


def test_hardware_command_plan_allows_unreadable_product_string_with_accepted_vid_pid() -> None:
    plan = HardwareCommandPlan(
        product_string=None,
        product_string_status="unreadable",
        vid=0x0403,
        pid=0x601E,
        command_scope="open-close",
        safety_reason="accepted VID/PID and explicit hardware approval",
        artifact="artifacts/n3dsxl/run/open_close.json",
        cleanup="release, close",
        command="uv run pytest tests/e2e/test_n3dsxl_open_close.py",
    )

    assert plan.is_allowed_n3dsxl_device()
