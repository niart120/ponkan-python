"""Project exception hierarchy."""

from dataclasses import dataclass


class CaptureError(Exception):
    """Base exception for py3dscapture failures."""


class UnsupportedDevice(CaptureError):  # noqa: N818
    """Raised when a USB device is not an accepted capture target."""


class DeviceOpenError(CaptureError):
    """Raised when opening or configuring a USB device fails."""


class InterfaceClaimError(DeviceOpenError):
    """Raised when claiming a required USB interface fails."""


@dataclass(frozen=True, slots=True)
class Ftd3CommandContext:
    """Debug context for one failed FTD3 command."""

    command_name: str
    pipe: int | None
    payload_length: int
    requested_length: int | None
    transferred: int | None
    libusb_status: int | None = None


class Ftd3CommandError(CaptureError):
    """Raised when an FTD3 command or transfer fails."""

    context: Ftd3CommandContext

    def __init__(self, context: Ftd3CommandContext) -> None:
        """Create an FTD3 command failure with structured context."""
        super().__init__(context.command_name)
        self.context = context


class UnsupportedOperation(CaptureError):  # noqa: N818
    """Raised when an operation is outside the current MVP scope."""
