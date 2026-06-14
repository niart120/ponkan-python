"""Public capture profile metadata registry."""

from dataclasses import dataclass
from typing import Literal

from ponkan.errors import CaptureError

SupportStatus = Literal["stable", "experimental"]


@dataclass(frozen=True, slots=True)
class CaptureProfile:
    """Public metadata describing one implemented capture profile."""

    id: str
    display_name: str
    model: str
    family: str
    provider: str
    support_status: SupportStatus
    default_output: str
    default_colorspace: str
    supported_colorspaces: tuple[str, ...]
    native_fps: float | None
    screen_layout: str
    supported_outputs: tuple[str, ...]
    supports_3d: bool
    supports_audio: bool
    supports_recording: bool
    aliases: tuple[str, ...] = ()


class UnknownCaptureProfile(CaptureError):  # noqa: N818
    """Raised when a profile id or alias is not present in the runtime registry."""

    def __init__(self, profile: str) -> None:
        """Create an error for an unknown capture profile id or alias."""
        super().__init__(
            f"unknown capture profile: {profile}",
            code="unsupported_profile",
            reason="unsupported_profile",
        )


_N3DSXL_PROFILE = CaptureProfile(
    id="n3dsxl",
    display_name="new 3DS XL",
    model="new_3ds_xl",
    family="3ds",
    provider="ponkan-python",
    support_status="stable",
    default_output="both_vertical",
    default_colorspace="RGB",
    supported_colorspaces=("RGB", "BGR"),
    native_fps=59.8,
    screen_layout="3ds_dual_screen",
    supported_outputs=("top", "bottom", "both_vertical"),
    supports_3d=False,
    supports_audio=False,
    supports_recording=False,
    aliases=("new_3ds_xl",),
)

_PROFILES = (_N3DSXL_PROFILE,)
_PROFILE_INDEX = {key: profile for profile in _PROFILES for key in (profile.id, *profile.aliases)}


def list_capture_profiles() -> tuple[CaptureProfile, ...]:
    """Return implemented runtime capture profiles without touching hardware."""
    return _PROFILES


def get_capture_profile(profile: str) -> CaptureProfile:
    """Return one capture profile by stable id or alias.

    Args:
        profile: Stable profile id or alias such as ``"n3dsxl"`` or
            ``"new_3ds_xl"``.

    Raises:
        UnknownCaptureProfile: The id or alias is not in the runtime registry.
    """
    try:
        return _PROFILE_INDEX[profile]
    except KeyError as exc:
        raise UnknownCaptureProfile(profile) from exc


__all__ = [
    "CaptureProfile",
    "SupportStatus",
    "UnknownCaptureProfile",
    "get_capture_profile",
    "list_capture_profiles",
]
