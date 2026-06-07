"""Capture frame data model."""

from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING, Literal, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from py3dscapture.errors import DecodeError, OptionalDependencyError
from py3dscapture.protocol.sizes import BOTTOM_WIDTH_3DS, HEIGHT_3DS, TOP_WIDTH_3DS

ColorSpace = Literal["RGB", "BGR"]
ScreenName = Literal["top", "bottom", "top_right"]
RGB8Array = NDArray[np.uint8]

if TYPE_CHECKING:
    from collections.abc import Callable


class PillowImageLike(Protocol):
    """Small Pillow Image surface used by callers and tools."""

    size: tuple[int, int]

    def save(self, fp: object) -> object:
        """Save the image."""
        ...


@dataclass(slots=True)
class CaptureFrame:
    """Decoded top and bottom screen frame."""

    top: RGB8Array
    bottom: RGB8Array
    top_right: RGB8Array | None
    timestamp_ns: int | None
    source_model: Literal["new_3ds_xl", "old_3ds"]
    mode_3d: bool
    sequence: int | None = None
    colorspace: ColorSpace = "RGB"

    def __post_init__(self) -> None:
        """Validate frame shapes, dtype, and internal color space."""
        _validate_rgb8(self.top, (HEIGHT_3DS, TOP_WIDTH_3DS, 3))
        _validate_rgb8(self.bottom, (HEIGHT_3DS, BOTTOM_WIDTH_3DS, 3))
        if self.top_right is not None:
            _validate_rgb8(self.top_right, (HEIGHT_3DS, TOP_WIDTH_3DS, 3))
        if self.colorspace != "RGB":
            raise DecodeError

    def to_ndarray(self, screen: ScreenName = "top", colorspace: ColorSpace = "RGB") -> RGB8Array:
        """Return one screen as RGB or BGR ndarray."""
        image = self._screen(screen)
        if colorspace == self.colorspace:
            return image.copy()
        if colorspace == "BGR" and self.colorspace == "RGB":
            return image[..., ::-1].copy()
        raise DecodeError

    def to_pillow(self, screen: ScreenName = "top") -> PillowImageLike:
        """Return one screen as a Pillow Image."""
        try:
            image_module = import_module("PIL.Image")
        except ImportError as exc:
            raise OptionalDependencyError("Pillow", "image") from exc
        fromarray = cast("Callable[..., PillowImageLike]", image_module.fromarray)
        return fromarray(self.to_ndarray(screen=screen, colorspace="RGB"), mode="RGB")

    def to_mosaic(self, gap: int = 0) -> RGB8Array:
        """Return top and centered bottom screens in one RGB image."""
        if gap < 0:
            raise ValueError
        width = TOP_WIDTH_3DS
        height = HEIGHT_3DS * 2 + gap
        mosaic = np.zeros((height, width, 3), dtype=np.uint8)
        mosaic[:HEIGHT_3DS, :TOP_WIDTH_3DS] = self.top
        bottom_x = (TOP_WIDTH_3DS - BOTTOM_WIDTH_3DS) // 2
        bottom_y = HEIGHT_3DS + gap
        mosaic[bottom_y : bottom_y + HEIGHT_3DS, bottom_x : bottom_x + BOTTOM_WIDTH_3DS] = (
            self.bottom
        )
        return mosaic

    def _screen(self, screen: ScreenName) -> RGB8Array:
        if screen == "top":
            return self.top
        if screen == "bottom":
            return self.bottom
        if screen == "top_right" and self.top_right is not None:
            return self.top_right
        raise DecodeError


def _validate_rgb8(array: RGB8Array, shape: tuple[int, int, int]) -> None:
    if array.shape != shape or array.dtype != np.uint8:
        raise DecodeError
