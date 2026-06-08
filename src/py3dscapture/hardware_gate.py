"""Hardware gate helpers for N3DSXL-only commands."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from py3dscapture.protocol.sizes import (
    ACCEPTED_N3DSXL_PRODUCT_IDS,
    ACCEPTED_N3DSXL_PRODUCT_STRINGS,
    N3DSXL_VENDOR_ID,
)


def requires_n3dsxl_tests_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether tests marked ``requires_n3dsxl`` should run.

    Args:
        env: Optional environment mapping for tests. ``os.environ`` is used when
            omitted.

    Returns:
        True only when ``PONKAN_RUN_N3DSXL`` is exactly ``"1"``.
    """
    return _env_flag("PONKAN_RUN_N3DSXL", env)


def performance_tests_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether tests marked ``performance`` should run.

    Args:
        env: Optional environment mapping for tests. ``os.environ`` is used when
            omitted.

    Returns:
        True only when ``PONKAN_RUN_PERFORMANCE`` is exactly ``"1"``.
    """
    return _env_flag("PONKAN_RUN_PERFORMANCE", env)


def manual_visual_tests_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether tests marked ``manual_visual`` should run.

    Args:
        env: Optional environment mapping for tests. ``os.environ`` is used when
            omitted.

    Returns:
        True only when ``PONKAN_RUN_MANUAL_VISUAL`` is exactly ``"1"``.
    """
    return _env_flag("PONKAN_RUN_MANUAL_VISUAL", env)


def hardware_approved(env: Mapping[str, str] | None = None) -> bool:
    """Return whether a human approved the current hardware command.

    Args:
        env: Optional environment mapping for tests. ``os.environ`` is used when
            omitted.

    Returns:
        True only when ``PONKAN_HARDWARE_APPROVED`` is exactly ``"1"``.
    """
    return _env_flag("PONKAN_HARDWARE_APPROVED", env)


def _env_flag(name: str, env: Mapping[str, str] | None) -> bool:
    values = os.environ if env is None else env
    return values.get(name) == "1"


@dataclass(frozen=True, slots=True)
class HardwareCommandPlan:
    """Human-reviewable plan for one hardware command boundary.

    Attributes:
        product_string: USB product string when readable.
        product_string_status: Whether the product string was accepted or could
            not be read.
        vid: USB vendor ID recorded for the device.
        pid: USB product ID recorded for the device.
        command_scope: Human-readable scope of the command to be run.
        safety_reason: Why the command is safe for the recorded device.
        artifact: Artifact path or description that will capture evidence.
        cleanup: Cleanup action expected after the command.
        command: Exact command requiring approval.
        backend_kind: Transport backend used by the command.
        driver_service: Optional Windows driver service observed for the device.
    """

    product_string: str | None
    product_string_status: Literal["accepted", "unreadable"]
    vid: int
    pid: int
    command_scope: str
    safety_reason: str
    artifact: str
    cleanup: str
    command: str
    backend_kind: Literal["libusb", "d3xx"] = "libusb"
    driver_service: str | None = None

    def is_allowed_n3dsxl_device(self) -> bool:
        """Return whether the recorded identity is allowed for N3DSXL commands.

        Product string ``None`` is allowed only when the status records it as
        unreadable; unsupported readable product strings are rejected.

        Returns:
            True when VID, PID, and product-string status satisfy the N3DSXL
            safety boundary.
        """
        product_string_allowed = (
            self.product_string in ACCEPTED_N3DSXL_PRODUCT_STRINGS
            if self.product_string is not None
            else self.product_string_status == "unreadable"
        )
        return (
            self.vid == N3DSXL_VENDOR_ID
            and self.pid in ACCEPTED_N3DSXL_PRODUCT_IDS
            and product_string_allowed
        )

    def to_dict(self) -> dict[str, str | None]:
        """Return a JSON-serializable command plan.

        Returns:
            A dictionary with VID and PID formatted as hexadecimal strings for
            artifact and review output.
        """
        return {
            "product_string": self.product_string,
            "product_string_status": self.product_string_status,
            "vid": f"0x{self.vid:04x}",
            "pid": f"0x{self.pid:04x}",
            "command_scope": self.command_scope,
            "safety_reason": self.safety_reason,
            "artifact": self.artifact,
            "cleanup": self.cleanup,
            "command": self.command,
            "backend_kind": self.backend_kind,
            "driver_service": self.driver_service,
        }
