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
        vid=0x0403,
        pid=0x601E,
        command_scope="performance",
        safety_reason="requires_n3dsxl marker and explicit hardware approval",
        artifact="artifacts/n3dsxl/20260607T120000/stream_stats.json",
        cleanup="cancel, drain, release, close",
        command='uv run pytest -m "requires_n3dsxl and performance" tests/performance',
    )

    assert plan.is_allowed_n3dsxl_device()
    assert plan.to_dict() == {
        "product_string": "N3DSXL",
        "vid": "0x0403",
        "pid": "0x601e",
        "command_scope": "performance",
        "safety_reason": "requires_n3dsxl marker and explicit hardware approval",
        "artifact": "artifacts/n3dsxl/20260607T120000/stream_stats.json",
        "cleanup": "cancel, drain, release, close",
        "command": 'uv run pytest -m "requires_n3dsxl and performance" tests/performance',
    }


def test_hardware_command_plan_rejects_non_n3dsxl_identity() -> None:
    plan = HardwareCommandPlan(
        product_string="OLD3DS",
        vid=0x0403,
        pid=0x601E,
        command_scope="performance",
        safety_reason="wrong product string",
        artifact="artifacts/n3dsxl/run/stream_stats.json",
        cleanup="cancel, drain, release, close",
        command="uv run pytest tests/performance",
    )

    assert not plan.is_allowed_n3dsxl_device()
