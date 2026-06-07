"""3DS RGB8 raw video layout decoders."""

from collections.abc import Iterable
from enum import IntEnum

import numpy as np

from py3dscapture.errors import DecodeError
from py3dscapture.image.frame import CaptureFrame
from py3dscapture.protocol.sizes import (
    BOTTOM_WIDTH_3DS,
    HEIGHT_3DS,
    TOP_WIDTH_3DS,
    video_size,
)


class DecoderVersion(IntEnum):
    """Candidate 2D decoder transforms."""

    RESHAPE_ONLY = 0
    TRANSPOSE = 1
    ROTATE90 = 2
    ROTATE90_FLIP = 3


def decode_rgb8_2d(raw_video: bytes | memoryview, *, decoder_version: int) -> CaptureFrame:
    """Decode 2D N3DSXL raw RGB8 bytes into top and bottom screens."""
    raw_bytes = bytes(raw_video)
    if len(raw_bytes) != video_size(mode_3d=False):
        raise DecodeError

    stacked = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(
        (TOP_WIDTH_3DS + BOTTOM_WIDTH_3DS, HEIGHT_3DS, 3)
    )
    top_source = stacked[:TOP_WIDTH_3DS]
    bottom_source = stacked[TOP_WIDTH_3DS:]
    version = DecoderVersion(decoder_version)
    return CaptureFrame(
        top=_transform_2d_source(top_source, version),
        bottom=_transform_2d_source(bottom_source, version),
        top_right=None,
        timestamp_ns=None,
        source_model="new_3ds_xl",
        mode_3d=False,
        colorspace="RGB",
    )


def iter_decoder_candidates(raw_video: bytes | memoryview) -> Iterable[tuple[int, CaptureFrame]]:
    """Yield all local 2D decoder candidates."""
    for version in DecoderVersion:
        yield int(version), decode_rgb8_2d(raw_video, decoder_version=int(version))


def _transform_2d_source(source: np.ndarray, version: DecoderVersion) -> np.ndarray:
    if version in {DecoderVersion.RESHAPE_ONLY, DecoderVersion.TRANSPOSE}:
        return source.transpose(1, 0, 2).copy()
    if version == DecoderVersion.ROTATE90:
        return np.rot90(source, k=-1).copy()
    if version == DecoderVersion.ROTATE90_FLIP:
        return np.flip(np.rot90(source, k=-1), axis=1).copy()
    raise DecodeError
