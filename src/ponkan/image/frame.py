"""Capture frame data model."""

from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING, Literal, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from ponkan.errors import DecodeError, OptionalDependencyError
from ponkan.protocol.sizes import BOTTOM_WIDTH_3DS, HEIGHT_3DS, TOP_WIDTH_3DS

ColorSpace = Literal["RGB", "BGR"]
ScreenName = Literal["top", "bottom", "top_right"]
RGB8Array = NDArray[np.uint8]

if TYPE_CHECKING:
    from collections.abc import Callable


class PillowImageLike(Protocol):
    """Small Pillow Image surface used by callers and tools.

    The protocol keeps Pillow optional at runtime while documenting the surface
    returned by ``CaptureFrame.to_pillow``.
    """

    size: tuple[int, int]

    def save(self, fp: object) -> object:
        """Save the image to a Pillow-supported file object or path.

        Args:
            fp: Destination accepted by ``PIL.Image.Image.save``.

        Returns:
            The value returned by Pillow's ``save`` implementation.
        """
        ...


@dataclass(slots=True)
class CaptureFrame:
    """Decoded RGB8 top and bottom screen frame.

    Attributes:
        top: Top screen image as ``uint8`` ndarray with shape ``(240, 400, 3)``.
        bottom: Bottom screen image as ``uint8`` ndarray with shape
            ``(240, 320, 3)``.
        top_right: Right-eye top screen for 3D captures, or ``None`` for 2D
            captures.
        timestamp_ns: Optional monotonic timestamp associated with the source
            transfer.
        source_model: Capture target model that produced this frame.
        mode_3d: Whether the frame came from 3D capture mode.
        sequence: Optional streaming sequence number.
        colorspace: Internal color channel order. Only ``"RGB"`` is accepted
            for stored frames.
    """

    top: RGB8Array
    bottom: RGB8Array
    top_right: RGB8Array | None
    timestamp_ns: int | None
    source_model: Literal["new_3ds_xl", "old_3ds"]
    mode_3d: bool
    sequence: int | None = None
    colorspace: ColorSpace = "RGB"

    def __post_init__(self) -> None:
        """Validate frame shapes, dtype, and internal color space.

        Raises:
            DecodeError: Any screen has an unexpected shape, non-``uint8`` dtype,
                or the stored color space is not RGB.
        """
        _validate_rgb8(self.top, (HEIGHT_3DS, TOP_WIDTH_3DS, 3))
        _validate_rgb8(self.bottom, (HEIGHT_3DS, BOTTOM_WIDTH_3DS, 3))
        if self.top_right is not None:
            _validate_rgb8(self.top_right, (HEIGHT_3DS, TOP_WIDTH_3DS, 3))
        if self.colorspace != "RGB":
            raise DecodeError

    def to_ndarray(self, screen: ScreenName = "top", colorspace: ColorSpace = "RGB") -> RGB8Array:
        """Return one screen as a copied RGB or BGR ndarray.

        Args:
            screen: Screen to return. ``"top_right"`` is valid only when the
                frame contains a 3D right-eye image.
            colorspace: Channel order for the returned copy.

        Returns:
            A copy of the requested screen with shape ``(height, width, 3)`` and
            dtype ``uint8``.

        Raises:
            DecodeError: The screen is unavailable, or the requested color space
                cannot be produced.
        """
        image = self._screen(screen)
        if colorspace == self.colorspace:
            return image.copy()
        if colorspace == "BGR" and self.colorspace == "RGB":
            return image[..., ::-1].copy()
        raise DecodeError

    def to_pillow(self, screen: ScreenName = "top") -> PillowImageLike:
        """Return one screen as a Pillow RGB image.

        Args:
            screen: Screen to convert. ``"top_right"`` is valid only when the
                frame contains a 3D right-eye image.

        Returns:
            A Pillow ``Image``-compatible object in RGB mode.

        Raises:
            OptionalDependencyError: Pillow is not installed.
            DecodeError: The requested screen is unavailable.
        """
        try:
            image_module = import_module("PIL.Image")
        except ImportError as exc:
            raise OptionalDependencyError("Pillow", "image") from exc
        fromarray = cast("Callable[..., PillowImageLike]", image_module.fromarray)
        return fromarray(self.to_ndarray(screen=screen, colorspace="RGB"), mode="RGB")

    def to_mosaic(self, gap: int = 0) -> RGB8Array:
        """Return top and centered bottom screens in one RGB image.

        Args:
            gap: Vertical black-space pixels inserted between top and bottom.

        Returns:
            A new RGB ndarray with the top screen first and the bottom screen
            centered under it.

        Raises:
            ValueError: ``gap`` is negative.
        """
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
