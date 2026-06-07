"""Project exception hierarchy."""


class CaptureError(Exception):
    """Base exception for py3dscapture failures."""


class UnsupportedDevice(CaptureError):  # noqa: N818
    """Raised when a USB device is not an accepted capture target."""


class DeviceOpenError(CaptureError):
    """Raised when opening or configuring a USB device fails."""


class InterfaceClaimError(DeviceOpenError):
    """Raised when claiming a required USB interface fails."""
