"""Python helpers for 3DS capture board frame acquisition."""

from importlib.metadata import PackageNotFoundError, version

from py3dscapture.protocol.sizes import (
    ACCEPTED_N3DSXL_PRODUCT_IDS,
    ACCEPTED_N3DSXL_PRODUCT_STRINGS,
    N3DSXL_VENDOR_ID,
    CaptureSizes,
    capture_sizes,
)

try:
    __version__ = version("ponkan-python")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "ACCEPTED_N3DSXL_PRODUCT_IDS",
    "ACCEPTED_N3DSXL_PRODUCT_STRINGS",
    "N3DSXL_VENDOR_ID",
    "CaptureSizes",
    "__version__",
    "capture_sizes",
]
