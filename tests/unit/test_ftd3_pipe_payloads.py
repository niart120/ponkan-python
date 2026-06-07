from typing import cast

import pytest

from py3dscapture.devices.n3dsxl_ftd3 import DeviceCandidate, N3DSXLDevice
from py3dscapture.errors import Ftd3CommandError, UnsupportedDevice
from py3dscapture.protocol.sizes import N3DSXL_BULK_IN_ENDPOINT, capture_size
from py3dscapture.transport.ftd3_pipe import (
    FTD3_COMMAND_CREATE_PIPE_ID,
    Ftd3Pipe,
    build_abort_pipe_payload,
    build_create_pipe_payload,
    build_prepare_read_payload,
    build_prepare_write_payload,
    build_set_stream_pipe_payload,
)
from py3dscapture.transport.libusb_backend import UsbDeviceInfo


class _FakeHandle:
    def __init__(self, *, short_command_write: bool = False) -> None:
        self.short_command_write = short_command_write
        self.calls: list[tuple[str, int, bytes | int, int]] = []

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
        self.calls.append(("bulk_write", endpoint, payload, timeout_ms))
        if self.short_command_write and endpoint == 0x01:
            return len(payload) - 1
        return len(payload)

    def bulk_read(self, endpoint: int, length: int, timeout_ms: int) -> bytes:
        self.calls.append(("bulk_read", endpoint, length, timeout_ms))
        return bytes(range(length))


def _session(handle: _FakeHandle | None = None) -> N3DSXLDevice:
    info = UsbDeviceInfo(
        bus_number=1,
        address=2,
        vendor_id=0x0403,
        product_id=0x601F,
        product_string="N3DSXL",
        serial_number="abc",
    )
    candidate = DeviceCandidate(info=info, product_string="N3DSXL")
    return N3DSXLDevice(
        candidate=candidate,
        handle=handle or _FakeHandle(),
        claimed_interfaces=(0, 1),
    )


def test_create_pipe_payload_matches_source_audit_fixture() -> None:
    assert build_create_pipe_payload(command_id=0) == bytes.fromhex(
        "00000000 82 03 0000 0000000000000000 00000000"
    )


def test_abort_pipe_payload_matches_source_audit_fixture() -> None:
    assert build_abort_pipe_payload(N3DSXL_BULK_IN_ENDPOINT, command_id=1) == bytes.fromhex(
        "01000000 82 00 0000 0000000000000000 00000000"
    )


def test_set_stream_pipe_payload_contains_2d_capture_size() -> None:
    assert build_set_stream_pipe_payload(
        N3DSXL_BULK_IN_ENDPOINT,
        capture_size(False),
        command_id=2,
    ) == bytes.fromhex("02000000 82 02 0000 00780800 0000000000000000")


def test_prepare_read_and_write_payloads_match_source_audit_fixture() -> None:
    assert build_prepare_read_payload(N3DSXL_BULK_IN_ENDPOINT, 0x10, command_id=3) == (
        bytes.fromhex("03000000 82 01 0000 10000000 0000000000000000")
    )
    assert build_prepare_write_payload(0x02, 4, command_id=4) == bytes.fromhex(
        "04000000 02 01 0000 04000000 0000000000000000"
    )


def test_read_pipe_prepares_then_bulk_reads() -> None:
    handle = _FakeHandle()
    pipe = Ftd3Pipe(_session(handle))

    data = pipe.read_pipe(N3DSXL_BULK_IN_ENDPOINT, 4)

    assert data == b"\x00\x01\x02\x03"
    assert handle.calls == [
        (
            "bulk_write",
            0x01,
            build_prepare_read_payload(N3DSXL_BULK_IN_ENDPOINT, 4, command_id=0),
            500,
        ),
        ("bulk_read", N3DSXL_BULK_IN_ENDPOINT, 4, 500),
    ]


def test_write_pipe_prepares_then_bulk_writes() -> None:
    handle = _FakeHandle()
    pipe = Ftd3Pipe(_session(handle))

    transferred = pipe.write_pipe(0x02, b"abcd")

    assert transferred == 4
    assert handle.calls == [
        ("bulk_write", 0x01, build_prepare_write_payload(0x02, 4, command_id=0), 500),
        ("bulk_write", 0x02, b"abcd", 500),
    ]


def test_non_n3dsxl_session_is_rejected_before_command_send() -> None:
    with pytest.raises(UnsupportedDevice):
        Ftd3Pipe(cast("N3DSXLDevice", object()))


def test_short_command_write_raises_structured_context() -> None:
    handle = _FakeHandle(short_command_write=True)
    pipe = Ftd3Pipe(_session(handle))

    with pytest.raises(Ftd3CommandError) as exc_info:
        pipe.create_pipe()

    assert exc_info.value.context.command_name == "create_pipe"
    assert exc_info.value.context.pipe == FTD3_COMMAND_CREATE_PIPE_ID
    assert exc_info.value.context.payload_length == 20
    assert exc_info.value.context.transferred == 19
