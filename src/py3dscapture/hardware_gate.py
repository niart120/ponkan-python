"""Hardware gate helpers for N3DSXL-only commands."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from py3dscapture.protocol.sizes import (
    ACCEPTED_N3DSXL_PRODUCT_IDS,
    ACCEPTED_N3DSXL_PRODUCT_STRINGS,
    N3DSXL_VENDOR_ID,
)


def requires_n3dsxl_tests_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether tests marked requires_n3dsxl should run."""
    return _env_flag("PONKAN_RUN_N3DSXL", env)


def performance_tests_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether tests marked performance should run."""
    return _env_flag("PONKAN_RUN_PERFORMANCE", env)


def hardware_approved(env: Mapping[str, str] | None = None) -> bool:
    """Return whether a human approved the current hardware command."""
    return _env_flag("PONKAN_HARDWARE_APPROVED", env)


def _env_flag(name: str, env: Mapping[str, str] | None) -> bool:
    values = os.environ if env is None else env
    return values.get(name) == "1"


@dataclass(frozen=True, slots=True)
class HardwareCommandPlan:
    """Human-reviewable plan for one hardware command boundary."""

    product_string: str
    vid: int
    pid: int
    command_scope: str
    safety_reason: str
    artifact: str
    cleanup: str
    command: str

    def is_allowed_n3dsxl_device(self) -> bool:
        """Return whether the recorded identity is allowed for N3DSXL commands."""
        return (
            self.vid == N3DSXL_VENDOR_ID
            and self.pid in ACCEPTED_N3DSXL_PRODUCT_IDS
            and self.product_string in ACCEPTED_N3DSXL_PRODUCT_STRINGS
        )

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serializable command plan."""
        return {
            "product_string": self.product_string,
            "vid": f"0x{self.vid:04x}",
            "pid": f"0x{self.pid:04x}",
            "command_scope": self.command_scope,
            "safety_reason": self.safety_reason,
            "artifact": self.artifact,
            "cleanup": self.cleanup,
            "command": self.command,
        }
