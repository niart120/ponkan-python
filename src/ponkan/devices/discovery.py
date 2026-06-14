"""Public capture device discovery model."""

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, cast

from ponkan.errors import CaptureReason, DependencyUnavailableError
from ponkan.profiles import UnknownCaptureProfile, get_capture_profile

if TYPE_CHECKING:
    from ponkan.transport.libusb_backend import LibusbBackend, UsbDeviceInfo

BackendPreference = Literal["auto", "d3xx", "d3xx-native", "libusb"]
BackendStatus = Literal["available", "unavailable", "unsupported"]
ConnectionStatus = Literal["available", "rejected", "unsupported", "unknown"]
IdStability = Literal["stable", "session", "unknown"]
ProductStringStatus = Literal["accepted", "unreadable", "rejected", "unknown"]

_VALID_BACKENDS = frozenset(("auto", "d3xx", "d3xx-native", "libusb"))


class _LibusbDiscoveryBackend(Protocol):
    def iter_devices(self) -> tuple["_UsbInfo", ...]:
        """Return descriptor-like USB device records without opening them."""
        ...


class _D3xxDiscoveryBackend(Protocol):
    def iter_devices(self) -> tuple[object, ...]:
        """Return D3XX descriptor-like device records without opening them."""
        ...


class _UsbInfo(Protocol):
    bus_number: int | None
    address: int | None
    vendor_id: int | None
    product_id: int | None
    product_string: str | None
    serial_number: str | None


class _CandidateInfo(Protocol):
    info: _UsbInfo
    product_string: str | None
    product_string_status: ProductStringStatus
    model: str


class _RejectedInfo(Protocol):
    info: _UsbInfo
    reason: str


class _D3xxDeviceInfo(Protocol):
    usb_info: _UsbInfo


@dataclass(frozen=True, slots=True)
class CaptureDeviceInfo:
    """Public descriptor and classification state for one visible device."""

    id: str
    display_name: str
    profile_id: str
    model: str
    backend: str
    backend_preference: BackendPreference
    vendor_id: int | None
    product_id: int | None
    serial_number: str | None
    product_string: str | None
    product_string_status: ProductStringStatus
    connection_status: ConnectionStatus
    id_stability: IdStability
    reason: CaptureReason = "available"
    remediation: str | None = None


@dataclass(frozen=True, slots=True)
class CaptureDeviceDiscovery:
    """Public discovery result for one profile/backend request."""

    profile_id: str
    backend_preference: BackendPreference
    resolved_backend: str
    backend_status: BackendStatus
    reason: CaptureReason = "available"
    remediation: str | None = None
    devices: tuple[CaptureDeviceInfo, ...] = ()


def resolve_backend_preference(
    backend: BackendPreference,
    *,
    sys_platform: str | None = None,
) -> str:
    """Resolve the concrete backend used by discovery and high-level open."""
    if backend != "auto":
        return backend
    platform = sys.platform if sys_platform is None else sys_platform
    if platform == "win32":
        return "d3xx-native"
    return "d3xx"


def list_capture_devices(
    *,
    profile: str = "n3dsxl",
    backend: BackendPreference | str = "auto",
    include_rejected: bool = False,
    _libusb_backend: object | None = None,
    _d3xx_backend: object | None = None,
    _sys_platform: str | None = None,
) -> CaptureDeviceDiscovery:
    """Return structured capture device discovery state without opening devices."""
    backend_preference = cast("BackendPreference", backend)
    if backend not in _VALID_BACKENDS:
        return CaptureDeviceDiscovery(
            profile_id=profile,
            backend_preference=backend_preference,
            resolved_backend=str(backend),
            backend_status="unsupported",
            reason="unsupported_backend",
        )
    try:
        profile_metadata = get_capture_profile(profile)
    except UnknownCaptureProfile:
        return CaptureDeviceDiscovery(
            profile_id=profile,
            backend_preference=backend_preference,
            resolved_backend=resolve_backend_preference(
                backend_preference,
                sys_platform=_sys_platform,
            ),
            backend_status="unsupported",
            reason="unsupported_profile",
        )

    resolved_backend = resolve_backend_preference(
        backend_preference,
        sys_platform=_sys_platform,
    )
    if profile_metadata.id != "n3dsxl":
        return CaptureDeviceDiscovery(
            profile_id=profile_metadata.id,
            backend_preference=backend_preference,
            resolved_backend=resolved_backend,
            backend_status="unsupported",
            reason="unsupported_profile",
        )
    if resolved_backend == "libusb":
        return _discover_libusb(
            profile_id=profile_metadata.id,
            backend_preference=backend_preference,
            resolved_backend=resolved_backend,
            include_rejected=include_rejected,
            backend=_libusb_backend,
        )
    if resolved_backend in ("d3xx", "d3xx-native"):
        return _discover_d3xx(
            profile_id=profile_metadata.id,
            backend_preference=backend_preference,
            resolved_backend=resolved_backend,
            include_rejected=include_rejected,
            backend=_d3xx_backend,
        )
    return CaptureDeviceDiscovery(
        profile_id=profile_metadata.id,
        backend_preference=backend_preference,
        resolved_backend=resolved_backend,
        backend_status="unsupported",
        reason="unsupported_backend",
    )


def _discover_libusb(
    *,
    profile_id: str,
    backend_preference: BackendPreference,
    resolved_backend: str,
    include_rejected: bool,
    backend: object | None,
) -> CaptureDeviceDiscovery:
    from ponkan.devices.n3dsxl_ftd3 import (  # noqa: PLC0415
        DeviceCandidate,
        RejectedDevice,
        list_n3dsxl_devices,
    )

    actual_backend = _new_libusb_backend() if backend is None else backend
    listing = list_n3dsxl_devices(cast("LibusbBackend", actual_backend))
    devices: list[CaptureDeviceInfo] = [
        _info_from_candidate(
            cast("_CandidateInfo", candidate),
            profile_id=profile_id,
            backend_preference=backend_preference,
            resolved_backend=resolved_backend,
        )
        for candidate in listing.candidates
        if isinstance(candidate, DeviceCandidate)
    ]
    if include_rejected:
        devices.extend(
            _info_from_rejected(
                cast("_RejectedInfo", rejected),
                profile_id=profile_id,
                backend_preference=backend_preference,
                resolved_backend=resolved_backend,
            )
            for rejected in listing.rejected
            if isinstance(rejected, RejectedDevice)
        )
    return _available_result(
        profile_id=profile_id,
        backend_preference=backend_preference,
        resolved_backend=resolved_backend,
        devices=tuple(devices),
        accepted_count=len(listing.candidates),
    )


def _discover_d3xx(
    *,
    profile_id: str,
    backend_preference: BackendPreference,
    resolved_backend: str,
    include_rejected: bool,
    backend: object | None,
) -> CaptureDeviceDiscovery:
    from ponkan.devices.n3dsxl_ftd3 import (  # noqa: PLC0415
        DeviceCandidate,
        RejectedDevice,
        classify_n3dsxl_device,
    )

    try:
        actual_backend = cast(
            "_D3xxDiscoveryBackend",
            _new_d3xx_backend() if backend is None else backend,
        )
        d3xx_devices = actual_backend.iter_devices()
    except DependencyUnavailableError as exc:
        return CaptureDeviceDiscovery(
            profile_id=profile_id,
            backend_preference=backend_preference,
            resolved_backend=resolved_backend,
            backend_status="unavailable",
            reason=exc.reason or "unknown",
            remediation=exc.remediation,
        )

    devices: list[CaptureDeviceInfo] = []
    accepted_count = 0
    for d3xx_device in d3xx_devices:
        usb_info = cast("_D3xxDeviceInfo", d3xx_device).usb_info
        classified = classify_n3dsxl_device(cast("UsbDeviceInfo", usb_info))
        if isinstance(classified, DeviceCandidate):
            accepted_count += 1
            devices.append(
                _info_from_candidate(
                    cast("_CandidateInfo", classified),
                    profile_id=profile_id,
                    backend_preference=backend_preference,
                    resolved_backend=resolved_backend,
                )
            )
        elif include_rejected and isinstance(classified, RejectedDevice):
            devices.append(
                _info_from_rejected(
                    cast("_RejectedInfo", classified),
                    profile_id=profile_id,
                    backend_preference=backend_preference,
                    resolved_backend=resolved_backend,
                )
            )
    return _available_result(
        profile_id=profile_id,
        backend_preference=backend_preference,
        resolved_backend=resolved_backend,
        devices=tuple(devices),
        accepted_count=accepted_count,
    )


def _available_result(
    *,
    profile_id: str,
    backend_preference: BackendPreference,
    resolved_backend: str,
    devices: tuple[CaptureDeviceInfo, ...],
    accepted_count: int,
) -> CaptureDeviceDiscovery:
    reason: CaptureReason = "available" if accepted_count else "device_not_found"
    return CaptureDeviceDiscovery(
        profile_id=profile_id,
        backend_preference=backend_preference,
        resolved_backend=resolved_backend,
        backend_status="available",
        reason=reason,
        devices=devices,
    )


def _info_from_candidate(
    candidate: _CandidateInfo,
    *,
    profile_id: str,
    backend_preference: BackendPreference,
    resolved_backend: str,
) -> CaptureDeviceInfo:
    info = candidate.info
    return CaptureDeviceInfo(
        id=_device_id(resolved_backend, info),
        display_name=candidate.product_string or "new 3DS XL",
        profile_id=profile_id,
        model=candidate.model,
        backend=resolved_backend,
        backend_preference=backend_preference,
        vendor_id=info.vendor_id,
        product_id=info.product_id,
        serial_number=info.serial_number,
        product_string=candidate.product_string,
        product_string_status=candidate.product_string_status,
        connection_status="available",
        id_stability=_id_stability(info),
    )


def _info_from_rejected(
    rejected: _RejectedInfo,
    *,
    profile_id: str,
    backend_preference: BackendPreference,
    resolved_backend: str,
) -> CaptureDeviceInfo:
    info = rejected.info
    return CaptureDeviceInfo(
        id=_device_id(resolved_backend, info),
        display_name=info.product_string or "Rejected FTDI device",
        profile_id=profile_id,
        model="unknown",
        backend=resolved_backend,
        backend_preference=backend_preference,
        vendor_id=info.vendor_id,
        product_id=info.product_id,
        serial_number=info.serial_number,
        product_string=info.product_string,
        product_string_status="rejected" if info.product_string else "unknown",
        connection_status="rejected",
        id_stability=_id_stability(info),
        reason="device_rejected",
        remediation=rejected.reason,
    )


def _device_id(backend: str, info: _UsbInfo) -> str:
    if info.serial_number:
        return f"{backend}:{info.serial_number}"
    if info.bus_number is not None and info.address is not None:
        return f"{backend}:bus{info.bus_number}:address{info.address}"
    if info.vendor_id is not None and info.product_id is not None:
        return f"{backend}:vid{info.vendor_id:04x}:pid{info.product_id:04x}"
    return f"{backend}:unknown"


def _id_stability(info: _UsbInfo) -> IdStability:
    if info.serial_number:
        return "stable"
    if info.bus_number is not None and info.address is not None:
        return "session"
    return "unknown"


def _new_libusb_backend() -> object:
    from ponkan.transport.libusb_backend import Usb1Backend  # noqa: PLC0415

    return Usb1Backend()


def _new_d3xx_backend() -> _D3xxDiscoveryBackend:
    from ponkan.transport.d3xx_backend import D3xxBackend  # noqa: PLC0415

    return D3xxBackend()


__all__ = [
    "BackendPreference",
    "BackendStatus",
    "CaptureDeviceDiscovery",
    "CaptureDeviceInfo",
    "ConnectionStatus",
    "IdStability",
    "ProductStringStatus",
    "list_capture_devices",
    "resolve_backend_preference",
]
