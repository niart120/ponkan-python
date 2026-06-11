# ruff: noqa: N802
import pytest

import ponkan.protocol.n3dsxl as n3dsxl_module
from ponkan.devices.n3dsxl_ftd3 import DeviceCandidate, N3DSXLDevice
from ponkan.errors import Ftd3CommandContext, Ftd3CommandError, UnsupportedOperation
from ponkan.protocol.n3dsxl import N3DSXL_CFG_WAIT_MS, N3DSXLProtocol
from ponkan.protocol.sizes import (
    N3DSXL_BULK_IN_ENDPOINT,
    N3DSXL_BULK_OUT_ENDPOINT,
    capture_size,
    video_size,
)
from ponkan.transport.d3xx_backend import D3xxHandle
from ponkan.transport.libusb_backend import UsbDeviceInfo


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

    def __init__(
        self,
        *,
        fail_on_set_stream: bool = False,
        reconnect_after_drain: bool = False,
        raw_reads: list[bytes] | None = None,
    ) -> None:
        self.fail_on_set_stream = fail_on_set_stream
        self.reconnect_after_drain_enabled = reconnect_after_drain
        self.raw_reads = raw_reads or []
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
        if length == capture_size(False) and self.raw_reads:
            return self.raw_reads.pop(0)
        return bytes(length)

    def write_pipe(self, pipe: int, payload: bytes, timeout_ms: int = 500) -> int:
        _ = timeout_ms
        self.calls.append(("write_pipe", pipe, payload))
        return len(payload)

    def reconnect_after_drain(self) -> None:
        if self.reconnect_after_drain_enabled:
            self.calls.append(("reconnect_after_drain", None, None))


class _UnusedD3xxBinding:
    FT_Pipe = object
    FT_Buffer = object

    def FT_CreateDeviceInfoList(self) -> tuple[int, int]:
        raise AssertionError

    def FT_GetDeviceInfoDetail(self, index: int) -> tuple[int, object]:
        _ = index
        raise AssertionError

    def FT_Create(self, identifier: object, open_flag: int, device: object) -> int:
        _ = identifier, open_flag, device
        raise AssertionError

    def FT_Close(self, device: object) -> int:
        _ = device
        return 0

    def FT_AbortPipe(self, device: object, pipe: object) -> int:
        _ = device, pipe
        raise AssertionError

    def FT_SetStreamPipe(
        self,
        device: object,
        all_write_pipes: bool,
        all_read_pipes: bool,
        pipe: object,
        stream_size: int,
    ) -> int:
        _ = device, all_write_pipes, all_read_pipes, pipe, stream_size
        raise AssertionError

    def FT_ReadPipe(
        self,
        device: object,
        pipe: object,
        buffer_length: int,
        overlapped_timeout_ms: int,
    ) -> tuple[int, object, int]:
        _ = device, pipe, buffer_length, overlapped_timeout_ms
        raise AssertionError

    def FT_ReadPipeEx(
        self,
        device: object,
        pipe: object,
        buffer_length: int,
        overlapped_timeout_ms: int,
    ) -> tuple[int, object, int]:
        _ = device, pipe, buffer_length, overlapped_timeout_ms
        raise AssertionError

    def FT_WritePipe(
        self,
        device: object,
        pipe: object,
        buffer: object,
        buffer_length: int,
        overlapped_timeout_ms: int,
    ) -> tuple[int, int]:
        _ = device, pipe, buffer, buffer_length, overlapped_timeout_ms
        raise AssertionError


def _device() -> N3DSXLDevice:
    info = UsbDeviceInfo(1, 2, 0x0403, 0x601F, "N3DSXL", "abc")
    candidate = DeviceCandidate(
        info=info,
        product_string="N3DSXL",
        product_string_status="accepted",
    )
    return N3DSXLDevice(candidate=candidate, handle=_UnusedHandle(), claimed_interfaces=(0, 1))


def _candidate() -> DeviceCandidate:
    return _device().candidate


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


def test_connect_reconnects_d3xx_handle_after_drain_when_supported() -> None:
    pipe = _FakePipe(reconnect_after_drain=True)
    protocol = N3DSXLProtocol(_device(), pipe)

    protocol.connect(mode_3d=False)

    assert pipe.calls[:4] == [
        ("create_pipe", None, None),
        ("write_pipe", N3DSXL_BULK_OUT_ENDPOINT, b"\x40\x80\x00\x00"),
        ("read_pipe", N3DSXL_BULK_IN_ENDPOINT, 0x100000),
        ("reconnect_after_drain", None, None),
    ]


def test_connect_waits_after_firmware_load(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(n3dsxl_module, "sleep", sleeps.append)
    pipe = _FakePipe()
    protocol = N3DSXLProtocol(_device(), pipe)

    protocol.connect(mode_3d=False)

    firmware_write_index = pipe.calls.index(
        ("write_pipe", N3DSXL_BULK_OUT_ENDPOINT, b"\x43\x00\x00\x00")
    )
    config_read_index = pipe.calls.index(
        ("write_pipe", N3DSXL_BULK_OUT_ENDPOINT, b"\x98\x05\x9f\x00")
    )
    assert sleeps == [N3DSXL_CFG_WAIT_MS / 1000]
    assert firmware_write_index < config_read_index


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


def test_raw_capture_skips_short_stream_reads() -> None:
    pipe = _FakePipe(raw_reads=[bytes(video_size(False) - 1), bytes(capture_size(False))])
    protocol = N3DSXLProtocol(_device(), pipe)

    capture = protocol.read_raw_frame(mode_3d=False)

    assert capture.transferred == capture_size(False)
    assert pipe.calls == [
        ("read_pipe", N3DSXL_BULK_IN_ENDPOINT, capture_size(False)),
        ("read_pipe", N3DSXL_BULK_IN_ENDPOINT, capture_size(False)),
    ]


def test_protocol_accepts_d3xx_handle_identity() -> None:
    handle = D3xxHandle(
        binding=_UnusedD3xxBinding(),
        device=object(),
        candidate=_candidate(),
    )

    protocol = N3DSXLProtocol(handle, _FakePipe())
    capture = protocol.read_raw_frame(mode_3d=False)

    assert capture.metadata["product_string"] == "N3DSXL"
