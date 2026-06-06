"""N3DSXL capture constants and raw frame size calculations."""

from dataclasses import dataclass
from typing import Final

N3DSXL_VENDOR_ID: Final = 0x0403
ACCEPTED_N3DSXL_PRODUCT_IDS: Final[frozenset[int]] = frozenset(
    {0x601E, 0x601F, 0x602A, 0x602B, 0x602C, 0x602D, 0x602F}
)
ACCEPTED_N3DSXL_PRODUCT_STRINGS: Final[frozenset[str]] = frozenset({"N3DSXL", "N3DSXL.2"})

N3DSXL_COMMAND_INTERFACE: Final = 0
N3DSXL_BULK_INTERFACE: Final = 1
N3DSXL_BULK_OUT_ENDPOINT: Final = 0x02
N3DSXL_BULK_IN_ENDPOINT: Final = 0x82
N3DSXL_FTD3_COMMAND_PIPE_ID: Final = 0x01
N3DSXL_DEFAULT_CONFIGURATION: Final = 1

TOP_WIDTH_3DS: Final = 400
BOTTOM_WIDTH_3DS: Final = 320
HEIGHT_3DS: Final = 240
RGB8_CHANNELS: Final = 3

N3DSXL_SAMPLES_IN: Final = 1096 * 16
AUDIO_SAMPLE_BYTES: Final = 2
AUDIO_SIZE_BYTES: Final = N3DSXL_SAMPLES_IN * AUDIO_SAMPLE_BYTES
UNUSED_BUFFER_SIZE_BYTES: Final = 1024
ERROR_BUFFER_SIZE_BYTES: Final = 1024
USB_CAPTURE_ALIGNMENT_BYTES: Final = 1024


@dataclass(frozen=True, slots=True)
class CaptureSizes:
    """Calculated raw capture sizes for one transfer mode."""

    mode_3d: bool
    video_size: int
    audio_size: int
    struct_total_before_1024_floor: int
    capture_size: int
    max_non_error_transferred: int


def video_size(mode_3d: bool) -> int:
    """Return RGB8 video payload bytes for 2D or 3D mode."""

    stacked_screen_width = TOP_WIDTH_3DS + BOTTOM_WIDTH_3DS
    if mode_3d:
        stacked_screen_width += TOP_WIDTH_3DS
    return HEIGHT_3DS * stacked_screen_width * RGB8_CHANNELS


def struct_total_before_1024_floor(mode_3d: bool) -> int:
    """Return the C capture struct size before cc3dsfs' 1024-byte floor operation."""

    return (
        video_size(mode_3d) + AUDIO_SIZE_BYTES + UNUSED_BUFFER_SIZE_BYTES + ERROR_BUFFER_SIZE_BYTES
    )


def capture_size(mode_3d: bool) -> int:
    """Return the transfer size after the 1024-byte floor operation."""

    total = struct_total_before_1024_floor(mode_3d)
    return (total // USB_CAPTURE_ALIGNMENT_BYTES) * USB_CAPTURE_ALIGNMENT_BYTES


def max_non_error_transferred(mode_3d: bool) -> int:
    """Return the largest transfer length that does not enter the error buffer."""

    return capture_size(mode_3d) - ERROR_BUFFER_SIZE_BYTES


def capture_sizes(mode_3d: bool) -> CaptureSizes:
    """Return all calculated size values for one transfer mode."""

    total = struct_total_before_1024_floor(mode_3d)
    transfer_size = capture_size(mode_3d)
    return CaptureSizes(
        mode_3d=mode_3d,
        video_size=video_size(mode_3d),
        audio_size=AUDIO_SIZE_BYTES,
        struct_total_before_1024_floor=total,
        capture_size=transfer_size,
        max_non_error_transferred=transfer_size - ERROR_BUFFER_SIZE_BYTES,
    )
