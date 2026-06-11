import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _PolicyModule(Protocol):
    violation_for_text: Callable[[str], str | None]


def _load_policy_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "ponkan_pre_tool_use_policy",
        _PROJECT_ROOT / ".codex" / "hooks" / "pre_tool_use_policy.py",
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _violation_for_text() -> Callable[[str], str | None]:
    return cast("_PolicyModule", _load_policy_module()).violation_for_text


@pytest.mark.parametrize(
    "command",
    [
        "uv run python -m ponkan.tools.capture_raw --out captures/raw.bin",
        "uv run python -m ponkan.tools.stream_n3dsxl --duration 10 --stats",
    ],
)
def test_ponkan_hardware_module_commands_require_approval(command: str) -> None:
    violation = _violation_for_text()(command)

    assert violation is not None
    assert "PONKAN_HARDWARE_APPROVED=1" in violation


def test_ponkan_hardware_module_command_allows_same_command_approval() -> None:
    violation = _violation_for_text()(
        "$env:PONKAN_HARDWARE_APPROVED=1; "
        "uv run python -m ponkan.tools.capture_raw --out captures/raw.bin"
    )

    assert violation is None
