"""3DS RGB8 raw video layout decoders."""

import numpy as np

from ponkan.errors import DecodeError
from ponkan.image.frame import CaptureFrame
from ponkan.protocol.sizes import (
    BOTTOM_WIDTH_3DS,
    HEIGHT_3DS,
    TOP_WIDTH_3DS,
    video_size,
)

APPROVED_N3DSXL_2D_DECODER_ID = "ftd3_cc3dsfs_2d"


def decode_rgb8_2d(raw_video: bytes | memoryview) -> CaptureFrame:
    """Decode 2D N3DSXL raw RGB8 bytes into top and bottom screens.

    Args:
        raw_video: Exact 2D RGB8 video region from an N3DSXL raw capture. The
            input must not include audio, unused, or error-buffer bytes.

    Returns:
        A decoded RGB ``CaptureFrame`` with top and bottom screens populated.

    Raises:
        DecodeError: The input length does not match the 2D video payload size.
    """
    raw_bytes = bytes(raw_video)
    if len(raw_bytes) != video_size(mode_3d=False):
        raise DecodeError

    stacked = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(
        (TOP_WIDTH_3DS + BOTTOM_WIDTH_3DS, HEIGHT_3DS, 3)
    )
    top_source, bottom_source = _split_ftd3_2d_source(stacked)
    return CaptureFrame(
        top=_transform_2d_source(top_source),
        bottom=_transform_2d_source(bottom_source),
        top_right=None,
        timestamp_ns=None,
        source_model="new_3ds_xl",
        mode_3d=False,
        colorspace="RGB",
    )


def _split_ftd3_2d_source(source: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    width_delta = TOP_WIDTH_3DS - BOTTOM_WIDTH_3DS
    top_source = np.empty((TOP_WIDTH_3DS, HEIGHT_3DS, 3), dtype=np.uint8)
    bottom_source = np.empty((BOTTOM_WIDTH_3DS, HEIGHT_3DS, 3), dtype=np.uint8)
    top_source[:width_delta] = source[:width_delta]
    bottom_source[:] = source[width_delta::2]
    top_source[width_delta:] = source[width_delta + 1 :: 2]
    return top_source, bottom_source


def _transform_2d_source(source: np.ndarray) -> np.ndarray:
    return np.rot90(source, k=1).copy()
