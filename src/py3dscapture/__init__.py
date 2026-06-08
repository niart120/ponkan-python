"""Python helpers for new 3DS XL capture board frame acquisition.

The package exposes the constants and size helpers needed to identify supported
N3DSXL capture boards and to reason about raw USB frame sizes. Higher-level
capture, decode, transport, and streaming APIs live in their dedicated
submodules.
"""

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
