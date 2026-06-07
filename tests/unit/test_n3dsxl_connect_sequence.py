import pytest

from py3dscapture.devices.n3dsxl_ftd3 import DeviceCandidate, N3DSXLDevice
from py3dscapture.errors import Ftd3CommandContext, Ftd3CommandError, UnsupportedOperation
from py3dscapture.protocol.n3dsxl import N3DSXLProtocol
from py3dscapture.protocol.sizes import (
    N3DSXL_BULK_IN_ENDPOINT,
    N3DSXL_BULK_OUT_ENDPOINT,
    capture_size,
)
from py3dscapture.transport.libusb_backend import UsbDeviceInfo


class _UnusedHandle:
    def detach_kernel_driver(self, interface: int) -> None:
        _ = interface

    def set_configuration(self, configuration: int) -> None:
        _ = configuration

    def claim_interface(self, interface: int) -> None:
        _ = interface

    def release_interface(self, interface: int) -> None:
        _ = interface

    def close(self) -> None:
        return

    def bulk_write(self, endpoint: int, payload: bytes, timeout_ms: int) -> int:
        _ = endpoint, timeout_ms
        return len(payload)

    def bulk_read(self, endpoint: int, length: int, timeout_ms: int) -> bytes:
        _ = endpoint, timeout_ms
        return bytes(length)


class _FakePipe:
    backend_kind = "d3xx"

    def __init__(self, *, fail_on_set_stream: bool = False) -> None:
        self.fail_on_set_stream = fail_on_set_stream
        self.calls: list[tuple[str, int | None, bytes | int | None]] = []

    def create_pipe(self) -> None:
        self.calls.append(("create_pipe", None, None))

    def abort_pipe(self, pipe: int) -> None:
        self.calls.append(("abort_pipe", pipe, None))

    def set_stream_pipe(self, pipe: int, length: int) -> None:
        self.calls.append(("set_stream_pipe", pipe, length))
        if self.fail_on_set_stream:
            raise Ftd3CommandError(
                Ftd3CommandContext(
                    command_name="set_stream_pipe",
                    pipe=pipe,
                    payload_length=20,
                    requested_length=length,
                    transferred=None,
                )
            )

    def read_pipe(self, pipe: int, length: int, timeout_ms: int = 500) -> bytes:
        _ = timeout_ms
        self.calls.append(("read_pipe", pipe, length))
        return bytes(length)

    def write_pipe(self, pipe: int, payload: bytes, timeout_ms: int = 500) -> int:
        _ = timeout_ms
        self.calls.append(("write_pipe", pipe, payload))
        return len(payload)


def _device() -> N3DSXLDevice:
    info = UsbDeviceInfo(1, 2, 0x0403, 0x601F, "N3DSXL", "abc")
    candidate = DeviceCandidate(
        info=info,
        product_string="N3DSXL",
        product_string_status="accepted",
    )
    return N3DSXLDevice(candidate=candidate, handle=_UnusedHandle(), claimed_interfaces=(0, 1))


def test_connect_rejects_3d_mode_for_mvp() -> None:
    protocol = N3DSXLProtocol(_device(), _FakePipe())

    with pytest.raises(UnsupportedOperation):
        protocol.connect(mode_3d=True)


def test_connect_sequence_reaches_2d_stream_setup() -> None:
    pipe = _FakePipe()
    protocol = N3DSXLProtocol(_device(), pipe)

    protocol.connect(mode_3d=False)

    assert pipe.calls[:4] == [
        ("create_pipe", None, None),
        ("write_pipe", N3DSXL_BULK_OUT_ENDPOINT, b"\x40\x80\x00\x00"),
        ("read_pipe", N3DSXL_BULK_IN_ENDPOINT, 0x100000),
        ("abort_pipe", N3DSXL_BULK_IN_ENDPOINT, None),
    ]
    assert pipe.calls[-3:] == [
        ("set_stream_pipe", N3DSXL_BULK_IN_ENDPOINT, capture_size(False)),
        ("abort_pipe", N3DSXL_BULK_IN_ENDPOINT, None),
        ("set_stream_pipe", N3DSXL_BULK_IN_ENDPOINT, capture_size(False)),
    ]


def test_connect_failure_preserves_ftd3_context() -> None:
    protocol = N3DSXLProtocol(_device(), _FakePipe(fail_on_set_stream=True))

    with pytest.raises(Ftd3CommandError) as exc_info:
        protocol.connect(mode_3d=False)

    assert exc_info.value.context.command_name == "set_stream_pipe"
    assert exc_info.value.context.requested_length == capture_size(False)


def test_raw_capture_metadata_includes_backend_identity() -> None:
    protocol = N3DSXLProtocol(_device(), _FakePipe())

    capture = protocol.read_raw_frame(mode_3d=False)

    assert capture.metadata["backend_kind"] == "d3xx"
