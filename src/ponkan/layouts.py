"""Public capture layout metadata registry."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from ponkan.errors import CaptureError
from ponkan.protocol.sizes import BOTTOM_WIDTH_3DS, HEIGHT_3DS, RGB8_CHANNELS, TOP_WIDTH_3DS

ScreenRole = Literal["primary", "touch"]


@dataclass(frozen=True, slots=True)
class ScreenInfo:
    """Public metadata for one logical screen in a capture layout."""

    id: str
    display_name: str
    width: int
    height: int
    channels: int
    colorspace: str
    coordinate_space: str
    role: ScreenRole

    @property
    def ndarray_shape(self) -> tuple[int, int, int]:
        """Return the image shape exposed by public frame APIs."""
        return (self.height, self.width, self.channels)


@dataclass(frozen=True, slots=True)
class CompositeOutputInfo:
    """Public metadata for one output returned by ``CaptureReader.read``."""

    id: str
    display_name: str
    width: int
    height: int
    channels: int
    screens: tuple[str, ...]
    placement: str
    default: bool = False

    @property
    def ndarray_shape(self) -> tuple[int, int, int]:
        """Return the ndarray shape produced for this output."""
        return (self.height, self.width, self.channels)


@dataclass(frozen=True, slots=True)
class CaptureLayout:
    """Public screen and output metadata for one capture profile layout."""

    id: str
    display_name: str
    screens: tuple[ScreenInfo, ...]
    outputs: tuple[CompositeOutputInfo, ...]
    aspect_hints: Mapping[str, object]


class UnknownCaptureLayout(CaptureError):  # noqa: N818
    """Raised when a capture layout id is not present in the runtime registry."""

    def __init__(self, layout_id: str) -> None:
        """Create an error for an unknown layout id."""
        super().__init__(
            f"unknown capture layout: {layout_id}",
            code="unsupported_layout",
        )


_N3DSXL_LAYOUT = CaptureLayout(
    id="3ds_dual_screen",
    display_name="3DS Dual Screen",
    screens=(
        ScreenInfo(
            id="top",
            display_name="Top Screen",
            width=TOP_WIDTH_3DS,
            height=HEIGHT_3DS,
            channels=RGB8_CHANNELS,
            colorspace="RGB",
            coordinate_space="top_pixels",
            role="primary",
        ),
        ScreenInfo(
            id="bottom",
            display_name="Bottom Screen",
            width=BOTTOM_WIDTH_3DS,
            height=HEIGHT_3DS,
            channels=RGB8_CHANNELS,
            colorspace="RGB",
            coordinate_space="bottom_pixels",
            role="touch",
        ),
    ),
    outputs=(
        CompositeOutputInfo(
            id="top",
            display_name="Top Screen",
            width=TOP_WIDTH_3DS,
            height=HEIGHT_3DS,
            channels=RGB8_CHANNELS,
            screens=("top",),
            placement="single",
        ),
        CompositeOutputInfo(
            id="bottom",
            display_name="Bottom Screen",
            width=BOTTOM_WIDTH_3DS,
            height=HEIGHT_3DS,
            channels=RGB8_CHANNELS,
            screens=("bottom",),
            placement="single",
        ),
        CompositeOutputInfo(
            id="both_vertical",
            display_name="Both Screens Vertical",
            width=TOP_WIDTH_3DS,
            height=HEIGHT_3DS * 2,
            channels=RGB8_CHANNELS,
            screens=("top", "bottom"),
            placement="top_above_bottom_centered",
            default=True,
        ),
    ),
    aspect_hints=MappingProxyType(
        {
            "pixel_aspect": "square",
            "bottom_horizontal_offset": (TOP_WIDTH_3DS - BOTTOM_WIDTH_3DS) // 2,
            "stereo_3d": "unsupported",
        }
    ),
)

_LAYOUTS = (_N3DSXL_LAYOUT,)
_LAYOUT_INDEX = {layout.id: layout for layout in _LAYOUTS}


def list_capture_layouts() -> tuple[CaptureLayout, ...]:
    """Return implemented capture layouts without touching hardware."""
    return _LAYOUTS


def get_capture_layout(layout_id: str) -> CaptureLayout:
    """Return one capture layout by stable id.

    Args:
        layout_id: Stable layout id such as ``"3ds_dual_screen"``.

    Raises:
        UnknownCaptureLayout: The id is not in the runtime registry.
    """
    try:
        return _LAYOUT_INDEX[layout_id]
    except KeyError as exc:
        raise UnknownCaptureLayout(layout_id) from exc


__all__ = [
    "CaptureLayout",
    "CompositeOutputInfo",
    "ScreenInfo",
    "ScreenRole",
    "UnknownCaptureLayout",
    "get_capture_layout",
    "list_capture_layouts",
]
