"""N3DSXL device filtering and session ownership."""

from contextlib import suppress
from dataclasses import dataclass
from typing import Literal, cast

from ponkan.errors import DeviceOpenError, UnsupportedDevice
from ponkan.protocol.sizes import (
    ACCEPTED_N3DSXL_PRODUCT_IDS,
    ACCEPTED_N3DSXL_PRODUCT_STRINGS,
    N3DSXL_BULK_INTERFACE,
    N3DSXL_COMMAND_INTERFACE,
    N3DSXL_DEFAULT_CONFIGURATION,
    N3DSXL_VENDOR_ID,
)
from ponkan.transport.libusb_backend import LibusbBackend, UsbDeviceInfo, UsbHandle

AcceptedProductString = Literal["N3DSXL", "N3DSXL.2"]
ProductStringStatus = Literal["accepted", "unreadable"]


@dataclass(frozen=True, slots=True)
class DeviceCandidate:
    """A USB device accepted as a new 3DS XL capture board.

    Attributes:
        info: USB descriptor information used to reopen the device.
        product_string: Accepted product string, or ``None`` when unreadable.
        product_string_status: Whether the product string was accepted or could
            not be read.
        model: Normalized device model exposed to higher layers.
    """

    info: UsbDeviceInfo
    product_string: AcceptedProductString | None
    product_string_status: ProductStringStatus
    model: Literal["new_3ds_xl"] = "new_3ds_xl"


@dataclass(frozen=True, slots=True)
class RejectedDevice:
    """An FTDI-family device rejected before N3DSXL commands can be sent.

    Attributes:
        info: USB descriptor information for the rejected device.
        reason: Stable rejection reason such as unsupported product ID or
            product string.
    """

    info: UsbDeviceInfo
    reason: str


@dataclass(frozen=True, slots=True)
class DeviceListing:
    """Classified devices for CLI and tests.

    Attributes:
        candidates: Devices allowed to proceed to the explicit hardware command
            approval boundary.
        rejected: FTDI-family devices that were deliberately excluded.
    """

    candidates: tuple[DeviceCandidate, ...]
    rejected: tuple[RejectedDevice, ...]


def classify_n3dsxl_device(info: UsbDeviceInfo) -> DeviceCandidate | RejectedDevice | None:
    """Classify one USB device as N3DSXL candidate, rejected FTDI device, or irrelevant.

    Args:
        info: USB descriptor fields gathered before opening the device.

    Returns:
        ``DeviceCandidate`` for accepted VID/PID and product string,
        ``RejectedDevice`` for FTDI-family devices that fail the N3DSXL safety
        boundary, or ``None`` for unrelated vendors.
    """
    if info.vendor_id != N3DSXL_VENDOR_ID:
        return None
    if info.product_id not in ACCEPTED_N3DSXL_PRODUCT_IDS:
        return RejectedDevice(info=info, reason="unsupported_product_id")
    if info.product_string is None:
        return DeviceCandidate(
            info=info,
            product_string=None,
            product_string_status="unreadable",
        )
    if info.product_string not in ACCEPTED_N3DSXL_PRODUCT_STRINGS:
        return RejectedDevice(info=info, reason="unsupported_product_string")
    return DeviceCandidate(
        info=info,
        product_string=cast("AcceptedProductString", info.product_string),
        product_string_status="accepted",
    )


def list_n3dsxl_devices(backend: LibusbBackend) -> DeviceListing:
    """Classify all devices visible through a backend.

    Args:
        backend: USB backend used only for enumeration.

    Returns:
        Candidate and rejected-device groups suitable for CLI output and tests.
    """
    candidates: list[DeviceCandidate] = []
    rejected: list[RejectedDevice] = []
    for info in backend.iter_devices():
        classified = classify_n3dsxl_device(info)
        if isinstance(classified, DeviceCandidate):
            candidates.append(classified)
        elif isinstance(classified, RejectedDevice):
            rejected.append(classified)
    return DeviceListing(candidates=tuple(candidates), rejected=tuple(rejected))


class N3DSXLDevice:
    """Open N3DSXL session owning claimed interfaces.

    The session assumes the input candidate already passed device
    classification. It owns interface release and handle close responsibility.
    """

    def __init__(
        self,
        candidate: DeviceCandidate,
        handle: UsbHandle,
        claimed_interfaces: tuple[int, ...],
    ) -> None:
        """Create a session from an already configured handle.

        Args:
            candidate: Accepted N3DSXL candidate used for metadata and safety
                reporting.
            handle: Opened USB handle whose required interfaces are claimed.
            claimed_interfaces: Interfaces this session must release on close.
        """
        self.candidate = candidate
        self.handle = handle
        self._claimed_interfaces = list(claimed_interfaces)
        self._closed = False

    @classmethod
    def open(
        cls,
        candidate: DeviceCandidate,
        backend: LibusbBackend,
    ) -> "N3DSXLDevice":
        """Open, configure, and claim a candidate device.

        Args:
            candidate: Accepted N3DSXL candidate.
            backend: USB backend used to open the descriptor.

        Returns:
            Open session owning command and bulk interfaces.

        Raises:
            UnsupportedDevice: ``candidate`` is not a ``DeviceCandidate``.
            DeviceOpenError: Opening, configuration, interface claim, cleanup, or
                final close fails through the backend.
        """
        if not isinstance(candidate, DeviceCandidate):
            raise UnsupportedDevice
        handle = backend.open(candidate.info)
        claimed_interfaces: list[int] = []
        try:
            for interface in (N3DSXL_COMMAND_INTERFACE, N3DSXL_BULK_INTERFACE):
                handle.detach_kernel_driver(interface)
            handle.set_configuration(N3DSXL_DEFAULT_CONFIGURATION)
            handle.claim_interface(N3DSXL_COMMAND_INTERFACE)
            claimed_interfaces.append(N3DSXL_COMMAND_INTERFACE)
            handle.claim_interface(N3DSXL_BULK_INTERFACE)
            claimed_interfaces.append(N3DSXL_BULK_INTERFACE)
        except Exception:
            _cleanup_failed_open(handle, claimed_interfaces)
            raise
        return cls(candidate=candidate, handle=handle, claimed_interfaces=tuple(claimed_interfaces))

    def close(self) -> None:
        """Release interfaces and close the handle.

        The method is idempotent for already closed sessions. If cleanup raises
        from more than one operation, the first cleanup error is re-raised as
        ``DeviceOpenError`` after all best-effort cleanup has run.

        Raises:
            DeviceOpenError: Interface release or handle close failed.
        """
        if self._closed:
            return

        first_error: Exception | None = None
        try:
            for interface in reversed(self._claimed_interfaces):
                try:
                    self.handle.release_interface(interface)
                except Exception as exc:  # noqa: BLE001  # pragma: no cover
                    if first_error is None:
                        first_error = exc
            self._claimed_interfaces.clear()
            try:
                self.handle.close()
            except Exception as exc:  # noqa: BLE001  # pragma: no cover
                if first_error is None:
                    first_error = exc
        finally:
            self._closed = True

        if first_error is not None:
            raise DeviceOpenError from first_error

    def __enter__(self) -> "N3DSXLDevice":
        """Return this active session for context-manager use.

        Returns:
            The open session itself.
        """
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        """Close the session when leaving a context manager.

        Args:
            exc_type: Exception type from the managed block, if any.
            exc: Exception instance from the managed block, if any.
            traceback: Traceback from the managed block, if any.
        """
        self.close()


def _cleanup_failed_open(handle: UsbHandle, claimed_interfaces: list[int]) -> None:
    for interface in reversed(claimed_interfaces):
        with suppress(Exception):
            handle.release_interface(interface)
    with suppress(Exception):
        handle.close()
