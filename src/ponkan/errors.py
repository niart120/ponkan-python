"""Project exception hierarchy."""

from dataclasses import dataclass


class CaptureError(Exception):
    """Base exception for ponkan failures.

    Catch this when callers want to handle package-level failures without
    matching individual USB, decode, or optional-dependency errors.
    """


class UnsupportedDevice(CaptureError):  # noqa: N818
    """Raised when a USB device is not an accepted capture target.

    The device failed the N3DSXL identity boundary or the object passed to a
    session API was not an accepted candidate.
    """


class DeviceNotFound(CaptureError):  # noqa: N818
    """Raised when no accepted capture device is visible to the selected backend."""


class DeviceOpenError(CaptureError):
    """Raised when opening or configuring a USB device fails.

    This covers backend open failures, configuration selection failures,
    interface claim failures, and cleanup failures during close.
    """


class InterfaceClaimError(DeviceOpenError):
    """Raised when claiming a required USB interface fails.

    Reserved for callers that need to distinguish interface ownership failures
    from other device-open errors.
    """


@dataclass(frozen=True, slots=True)
class Ftd3CommandContext:
    """Debug context for one failed FTD3 command.

    Attributes:
        command_name: Logical command or transfer name.
        pipe: Pipe or endpoint associated with the failure, if known.
        payload_length: Command payload length in bytes.
        requested_length: Requested transfer length in bytes, if applicable.
        transferred: Number of bytes reported by the backend, if available.
        libusb_status: Optional libusb status code for async paths.
    """

    command_name: str
    pipe: int | None
    payload_length: int
    requested_length: int | None
    transferred: int | None
    libusb_status: int | None = None


class Ftd3CommandError(CaptureError):
    """Raised when an FTD3 command or transfer fails.

    Attributes:
        context: Structured command context for logs and artifact metadata.
    """

    context: Ftd3CommandContext

    def __init__(self, context: Ftd3CommandContext) -> None:
        """Create an FTD3 command failure with structured context.

        Args:
            context: Structured command details captured at the failure point.
        """
        super().__init__(context.command_name)
        self.context = context


class UnsupportedOperation(CaptureError):  # noqa: N818
    """Raised when an operation is outside the current MVP scope.

    Examples include requesting 3D capture while the implementation is limited
    to 2D new 3DS XL frame acquisition.
    """


class TransferOverflow(CaptureError):  # noqa: N818
    """Raised when a transfer length is outside the accepted capture bounds.

    The transport reported more bytes than the selected raw capture structure
    allows.
    """


class DecodeError(CaptureError):
    """Raised when raw frame data cannot be decoded.

    This covers short raw captures, unexpected frame shapes or dtypes, invalid
    color-space requests, and unsupported screen selection.
    """


class OptionalDependencyError(CaptureError):
    """Raised when an optional adapter dependency is missing.

    Optional extras currently include image conversion dependencies and the D3XX
    backend dependency.
    """

    def __init__(self, dependency: str, extra: str) -> None:
        """Create an optional dependency error.

        Args:
            dependency: Human-readable dependency name.
            extra: Project extra that installs the dependency.
        """
        super().__init__(f"Install {dependency} or use the {extra} extra.")
