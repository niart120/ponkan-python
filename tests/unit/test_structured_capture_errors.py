from typing import get_args

from ponkan.errors import (
    CaptureError,
    CaptureReason,
    DecodeError,
    DependencyUnavailableError,
    DeviceNotFound,
    DeviceOpenError,
    Ftd3CommandContext,
    Ftd3CommandError,
    UnsupportedDevice,
    UnsupportedOperation,
)
from ponkan.profiles import UnknownCaptureProfile
from ponkan.transport.d3xx_backend import D3xxBackendError


def test_capture_error_has_common_fields_and_preserves_message() -> None:
    error = CaptureError(
        "device is unavailable",
        code="device_not_found",
        profile="n3dsxl",
        backend="d3xx-native",
        reason="device_not_found",
        recoverable=True,
        remediation="Connect an accepted N3DSXL capture board.",
    )

    assert str(error) == "device is unavailable"
    assert error.code == "device_not_found"
    assert error.profile == "n3dsxl"
    assert error.backend == "d3xx-native"
    assert error.reason == "device_not_found"
    assert error.recoverable is True
    assert error.remediation == "Connect an accepted N3DSXL capture board."


def test_subclasses_have_stable_default_codes() -> None:
    assert DeviceNotFound().code == "device_not_found"
    assert DeviceNotFound().reason == "device_not_found"
    assert DeviceNotFound().recoverable is True

    assert UnsupportedDevice().code == "device_rejected"
    assert UnsupportedDevice().reason == "device_rejected"
    assert UnsupportedDevice().recoverable is False

    assert DeviceOpenError().code == "open_failed"
    assert DeviceOpenError().reason == "open_failed"
    assert DeviceOpenError().recoverable is True

    assert UnsupportedOperation().code == "unsupported_operation"
    assert UnsupportedOperation().recoverable is False

    assert DecodeError().code == "decode_failed"
    assert DecodeError().reason == "decode_failed"
    assert DecodeError().recoverable is False


def test_str_error_preserves_custom_message() -> None:
    assert str(DeviceOpenError("LIBUSB_ERROR_NOT_FOUND [-5]")) == "LIBUSB_ERROR_NOT_FOUND [-5]"


def test_dependency_unavailable_backend_error_has_context() -> None:
    error = DependencyUnavailableError.for_backend_dependency("PyD3XX", "d3xx")

    assert error.code == "dependency_unavailable"
    assert error.backend == "d3xx"
    assert error.reason == "missing_package"
    assert error.recoverable is True
    assert error.remediation is not None
    assert "PyD3XX is required for the d3xx backend" in str(error)


def test_ftd3_command_error_keeps_context_and_common_fields() -> None:
    context = Ftd3CommandContext(
        command_name="prepare_read",
        pipe=0x82,
        payload_length=20,
        requested_length=555008,
        transferred=19,
        libusb_status=-7,
    )

    error = Ftd3CommandError(context)

    assert str(error) == "prepare_read"
    assert error.context is context
    assert error.code == "ftd3_command_failed"
    assert error.reason == "read_failed"
    assert error.recoverable is True


def test_d3xx_backend_error_has_common_fields_and_context() -> None:
    error = D3xxBackendError("FT_Create", 1)

    assert str(error) == "FT_Create failed with status 1"
    assert error.code == "d3xx_backend_failed"
    assert error.backend == "d3xx"
    assert error.reason == "open_failed"
    assert error.recoverable is True
    assert error.function == "FT_Create"
    assert error.status == 1
    assert error.field_name is None


def test_d3xx_backend_missing_field_has_read_failure_context() -> None:
    error = D3xxBackendError.missing_field("Description")

    assert str(error) == "missing field: Description"
    assert error.code == "d3xx_backend_failed"
    assert error.backend == "d3xx"
    assert error.reason == "read_failed"
    assert error.recoverable is True
    assert error.function == "missing field"
    assert error.status is None
    assert error.field_name == "Description"


def test_d3xx_backend_factory_reasons_are_stable() -> None:
    invalid_integer = D3xxBackendError.invalid_integer("ID")
    invalid_candidate = D3xxBackendError.invalid_candidate()

    assert invalid_integer.code == "d3xx_backend_failed"
    assert invalid_integer.reason == "read_failed"
    assert invalid_integer.function == "invalid integer"
    assert invalid_integer.field_name == "ID"

    assert invalid_candidate.code == "d3xx_backend_failed"
    assert invalid_candidate.reason == "open_failed"
    assert invalid_candidate.function == "invalid candidate"
    assert invalid_candidate.status is None
    assert invalid_candidate.field_name is None


def test_unknown_capture_profile_uses_shared_reason() -> None:
    error = UnknownCaptureProfile("classic_ds")

    assert error.code == "unsupported_profile"
    assert error.reason == "unsupported_profile"
    assert str(error) == "unknown capture profile: classic_ds"


def test_error_fields_are_json_log_friendly() -> None:
    error = CaptureError(
        "decode failed",
        code="decode_failed",
        profile="n3dsxl",
        backend="d3xx",
        reason="decode_failed",
        recoverable=False,
        remediation=None,
    )

    assert error.to_dict() == {
        "message": "decode failed",
        "code": "decode_failed",
        "profile": "n3dsxl",
        "backend": "d3xx",
        "reason": "decode_failed",
        "recoverable": False,
        "remediation": None,
    }


def test_capture_reason_values_cover_discovery_and_error_reasons() -> None:
    assert set(get_args(CaptureReason)) == {
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
    }
