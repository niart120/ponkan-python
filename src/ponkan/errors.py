"""Project exception hierarchy."""

from dataclasses import dataclass
from typing import ClassVar, Literal

CaptureReason = Literal[
    "available",
    "missing_package",
    "missing_driver",
    "missing_runtime",
    "unsupported_platform",
    "unsupported_backend",
    "unsupported_profile",
    "device_not_found",
    "device_rejected",
    "open_failed",
    "read_failed",
    "decode_failed",
    "unknown",
]


class CaptureError(Exception):
    """Base exception for ponkan failures.

    Catch this when callers want to handle package-level failures without
    matching individual USB, decode, or optional-dependency errors.
    """

    DEFAULT_CODE: ClassVar[str] = "capture_error"
    DEFAULT_REASON: ClassVar[CaptureReason | None] = None
    DEFAULT_RECOVERABLE: ClassVar[bool] = False

    code: str
    profile: str | None
    backend: str | None
    reason: CaptureReason | None
    recoverable: bool
    remediation: str | None

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        profile: str | None = None,
        backend: str | None = None,
        reason: CaptureReason | None = None,
        recoverable: bool | None = None,
        remediation: str | None = None,
    ) -> None:
        """Create a package error with machine-readable context."""
        if message is None:
            super().__init__()
        else:
            super().__init__(message)
        self.code = self.DEFAULT_CODE if code is None else code
        self.profile = profile
        self.backend = backend
        self.reason = self.DEFAULT_REASON if reason is None else reason
        self.recoverable = self.DEFAULT_RECOVERABLE if recoverable is None else recoverable
        self.remediation = remediation

    def to_dict(self) -> dict[str, object]:
        """Return JSON-friendly structured error fields."""
        return {
            "message": str(self),
            "code": self.code,
            "profile": self.profile,
            "backend": self.backend,
            "reason": self.reason,
            "recoverable": self.recoverable,
            "remediation": self.remediation,
        }


class UnsupportedDevice(CaptureError):  # noqa: N818
    """Raised when a USB device is not an accepted capture target.

    The device failed the N3DSXL identity boundary or the object passed to a
    session API was not an accepted candidate.
    """

    DEFAULT_CODE: ClassVar[str] = "device_rejected"
    DEFAULT_REASON: ClassVar[CaptureReason | None] = "device_rejected"


class DeviceNotFound(CaptureError):  # noqa: N818
    """Raised when no accepted capture device is visible to the selected backend."""

    DEFAULT_CODE: ClassVar[str] = "device_not_found"
    DEFAULT_REASON: ClassVar[CaptureReason | None] = "device_not_found"
    DEFAULT_RECOVERABLE: ClassVar[bool] = True


class DeviceOpenError(CaptureError):
    """Raised when opening or configuring a USB device fails.

    This covers backend open failures, configuration selection failures,
    interface claim failures, and cleanup failures during close.
    """

    DEFAULT_CODE: ClassVar[str] = "open_failed"
    DEFAULT_REASON: ClassVar[CaptureReason | None] = "open_failed"
    DEFAULT_RECOVERABLE: ClassVar[bool] = True


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
        super().__init__(
            context.command_name,
            code="ftd3_command_failed",
            reason="read_failed",
            recoverable=True,
        )
        self.context = context


class UnsupportedOperation(CaptureError):  # noqa: N818
    """Raised when an operation is outside the current MVP scope.

    Examples include requesting 3D capture while the implementation is limited
    to 2D new 3DS XL frame acquisition.
    """

    DEFAULT_CODE: ClassVar[str] = "unsupported_operation"


class TransferOverflow(CaptureError):  # noqa: N818
    """Raised when a transfer length is outside the accepted capture bounds.

    The transport reported more bytes than the selected raw capture structure
    allows.
    """

    DEFAULT_CODE: ClassVar[str] = "transfer_overflow"
    DEFAULT_REASON: ClassVar[CaptureReason | None] = "read_failed"


class DecodeError(CaptureError):
    """Raised when raw frame data cannot be decoded.

    This covers short raw captures, unexpected frame shapes or dtypes, invalid
    color-space requests, and unsupported screen selection.
    """

    DEFAULT_CODE: ClassVar[str] = "decode_failed"
    DEFAULT_REASON: ClassVar[CaptureReason | None] = "decode_failed"


class DependencyUnavailableError(CaptureError):
    """Raised when a runtime dependency required by a selected path is missing.

    This covers platform-gated normal dependencies as well as more specific
    optional-extra dependencies.
    """

    DEFAULT_CODE: ClassVar[str] = "dependency_unavailable"
    DEFAULT_REASON: ClassVar[CaptureReason | None] = "missing_package"
    DEFAULT_RECOVERABLE: ClassVar[bool] = True

    @classmethod
    def for_backend_dependency(
        cls,
        dependency: str,
        backend: str,
    ) -> "DependencyUnavailableError":
        """Create an error for a dependency required by one backend."""
        remediation = (
            "Install ponkan-python with dependencies for this platform, or select a "
            "backend supported by this environment."
        )
        return cls(
            f"{dependency} is required for the {backend} backend. {remediation}",
            backend=backend,
            reason="missing_package",
            remediation=remediation,
        )


class OptionalDependencyError(DependencyUnavailableError):
    """Raised when a dependency provided by an optional extra is missing.

    Optional extras currently include image conversion dependencies.
    """

    def __init__(self, dependency: str, extra: str) -> None:
        """Create an optional dependency error.

        Args:
            dependency: Human-readable dependency name.
            extra: Project extra that installs the dependency.
        """
        remediation = f"Install {dependency} or use the {extra} extra."
        super().__init__(remediation, reason="missing_package", remediation=remediation)
