"""Python helpers for new 3DS XL capture board frame acquisition.

The package exposes the constants and size helpers needed to identify supported
N3DSXL capture boards and to reason about raw USB frame sizes. Higher-level
capture, decode, transport, and streaming APIs live in their dedicated
submodules.
"""

from importlib.metadata import PackageNotFoundError, version

from ponkan.capture import CaptureConfig, CaptureOutput, CaptureReader, open_capture
from ponkan.devices.discovery import (
    CaptureDeviceDiscovery,
    CaptureDeviceInfo,
    list_capture_devices,
)
from ponkan.layouts import (
    CaptureLayout,
    CompositeOutputInfo,
    ScreenInfo,
    get_capture_layout,
    list_capture_layouts,
)
from ponkan.profiles import CaptureProfile, get_capture_profile, list_capture_profiles
from ponkan.protocol.sizes import (
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
    "CaptureConfig",
    "CaptureDeviceDiscovery",
    "CaptureDeviceInfo",
    "CaptureLayout",
    "CaptureOutput",
    "CaptureProfile",
    "CaptureReader",
    "CaptureSizes",
    "CompositeOutputInfo",
    "ScreenInfo",
    "__version__",
    "capture_sizes",
    "get_capture_layout",
    "get_capture_profile",
    "list_capture_devices",
    "list_capture_layouts",
    "list_capture_profiles",
    "open_capture",
]
