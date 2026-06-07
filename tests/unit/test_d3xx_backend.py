# ruff: noqa: N802
from dataclasses import dataclass

import pytest

import py3dscapture.transport.d3xx_backend as d3xx_backend
from py3dscapture.devices.n3dsxl_ftd3 import DeviceCandidate
from py3dscapture.errors import OptionalDependencyError
from py3dscapture.transport.d3xx_backend import D3xxBackend


@dataclass(frozen=True, slots=True)
class _FakeD3xxInfo:
    ID: int
    Description: str | None
    SerialNumber: str | None
    Flags: int = 0


class _FakeD3xxPipe:
    def __init__(self) -> None:
        self.PipeID = 0
        self._PipeID = 0


class _FakeD3xxBuffer:
    def __init__(self, payload: bytes = b"") -> None:
        self.payload = payload

    @classmethod
    def from_bytes(cls, payload: bytes) -> "_FakeD3xxBuffer":
        return cls(payload)

    def Value(self) -> bytearray:
        return bytearray(self.payload)


class _FakeD3xxBinding:
    FT_Pipe = _FakeD3xxPipe
    FT_Buffer = _FakeD3xxBuffer

    def __init__(self) -> None:
        self.detail_indexes: list[int] = []
        self.created: list[tuple[object, int, _FakeD3xxInfo]] = []
        self.closed: list[_FakeD3xxInfo] = []
        self.aborted: list[tuple[_FakeD3xxInfo, int]] = []
        self.stream_pipes: list[tuple[_FakeD3xxInfo, bool, bool, int, int]] = []
        self.reads: list[tuple[_FakeD3xxInfo, int, int, int]] = []
        self.stream_reads: list[tuple[_FakeD3xxInfo, int, int, int]] = []
        self.writes: list[tuple[_FakeD3xxInfo, int, bytes, int, int]] = []

    def FT_CreateDeviceInfoList(self) -> tuple[int, int]:
        return 0, 3

    def FT_GetDeviceInfoDetail(self, index: int) -> tuple[int, _FakeD3xxInfo]:
        self.detail_indexes.append(index)
        if index == 0:
            return 0, _FakeD3xxInfo(0x0403601E, "N3DSXL.2", "NXL530228")
        if index == 1:
            return 0, _FakeD3xxInfo(0x0403601E, "FTDI SuperSpeed-FIFO Bridge", "FT600")
        return 0, _FakeD3xxInfo(0x0403601E, None, None)

    def FT_Create(self, identifier: object, open_flag: int, device: object) -> int:
        if not isinstance(device, _FakeD3xxInfo):
            raise TypeError
        self.created.append((identifier, open_flag, device))
        return 0

    def FT_Close(self, device: object) -> int:
        if not isinstance(device, _FakeD3xxInfo):
            raise TypeError
        self.closed.append(device)
        return 0

    def FT_AbortPipe(self, device: object, pipe: object) -> int:
        if not isinstance(device, _FakeD3xxInfo) or not isinstance(pipe, _FakeD3xxPipe):
            raise TypeError
        self.aborted.append((device, pipe.PipeID))
        return 0

    def FT_SetStreamPipe(
        self,
        device: object,
        all_write_pipes: bool,
        all_read_pipes: bool,
        pipe: object,
        stream_size: int,
    ) -> int:
        if not isinstance(device, _FakeD3xxInfo) or not isinstance(pipe, _FakeD3xxPipe):
            raise TypeError
        self.stream_pipes.append(
            (device, all_write_pipes, all_read_pipes, pipe.PipeID, stream_size)
        )
        return 0

    def FT_ReadPipe(
        self,
        device: object,
        pipe: object,
        buffer_length: int,
        overlapped_timeout_ms: int,
    ) -> tuple[int, _FakeD3xxBuffer, int]:
        if not isinstance(device, _FakeD3xxInfo) or not isinstance(pipe, _FakeD3xxPipe):
            raise TypeError
        self.reads.append((device, pipe.PipeID, buffer_length, overlapped_timeout_ms))
        return 0, _FakeD3xxBuffer(b"abcdef"), 4

    def FT_ReadPipeEx(
        self,
        device: object,
        pipe: object,
        buffer_length: int,
        overlapped_timeout_ms: int,
    ) -> tuple[int, _FakeD3xxBuffer, int]:
        if not isinstance(device, _FakeD3xxInfo) or not isinstance(pipe, _FakeD3xxPipe):
            raise TypeError
        self.stream_reads.append((device, pipe.PipeID, buffer_length, overlapped_timeout_ms))
        return 0, _FakeD3xxBuffer(b"stream"), 6

    def FT_WritePipe(
        self,
        device: object,
        pipe: object,
        buffer: object,
        buffer_length: int,
        overlapped_timeout_ms: int,
    ) -> tuple[int, int]:
        if (
            not isinstance(device, _FakeD3xxInfo)
            or not isinstance(pipe, _FakeD3xxPipe)
            or not isinstance(buffer, _FakeD3xxBuffer)
        ):
            raise TypeError
        self.writes.append(
            (device, pipe.PipeID, bytes(buffer.Value()), buffer_length, overlapped_timeout_ms)
        )
        return 0, buffer_length


def test_d3xx_binding_fake_lists_n3dsxl_candidate() -> None:
    binding = _FakeD3xxBinding()

    candidates = D3xxBackend(binding).iter_device_candidates()

    assert binding.detail_indexes == [0, 1, 2]
    assert len(candidates) == 2
    assert isinstance(candidates[0].candidate, DeviceCandidate)
    assert candidates[0].candidate.info.vendor_id == 0x0403
    assert candidates[0].candidate.info.product_id == 0x601E
    assert candidates[0].candidate.product_string == "N3DSXL.2"
    assert candidates[0].candidate.product_string_status == "accepted"
    assert candidates[0].index == 0
    assert candidates[1].candidate.product_string is None
    assert candidates[1].candidate.product_string_status == "unreadable"
    assert candidates[1].index == 2


def test_d3xx_open_uses_initialized_detail_and_close_is_idempotent() -> None:
    binding = _FakeD3xxBinding()
    backend = D3xxBackend(binding)
    candidate = backend.iter_device_candidates()[0]
    binding.detail_indexes.clear()

    handle = backend.open(candidate)
    handle.close()
    handle.close()

    assert binding.detail_indexes == [0]
    assert binding.created == [
        ("NXL530228", 0x01, _FakeD3xxInfo(0x0403601E, "N3DSXL.2", "NXL530228"))
    ]
    assert binding.closed == [_FakeD3xxInfo(0x0403601E, "N3DSXL.2", "NXL530228")]


def test_d3xx_reconnect_after_drain_closes_and_reopens_same_candidate() -> None:
    binding = _FakeD3xxBinding()
    backend = D3xxBackend(binding)
    candidate = backend.iter_device_candidates()[0]
    handle = backend.open(candidate)
    binding.detail_indexes.clear()
    binding.created.clear()
    binding.closed.clear()

    handle.reconnect_after_drain()

    device = _FakeD3xxInfo(0x0403601E, "N3DSXL.2", "NXL530228")
    assert binding.closed == [device]
    assert binding.detail_indexes == [0]
    assert binding.created == [("NXL530228", 0x01, device)]


def test_d3xx_pipe_methods_call_native_d3xx_api() -> None:
    binding = _FakeD3xxBinding()
    backend = D3xxBackend(binding)
    handle = backend.open(backend.iter_device_candidates()[0])
    device = _FakeD3xxInfo(0x0403601E, "N3DSXL.2", "NXL530228")

    handle.abort_pipe(0x82)
    read_data = handle.read_pipe(0x82, 8, 500)
    handle.set_stream_pipe(0x82, 1024)
    written = handle.write_pipe(0x82, b"payload", 500)

    assert binding.aborted == [(device, 0x82)]
    assert binding.stream_pipes == [(device, False, False, 0x82, 1024)]
    assert binding.reads == [(device, 0x82, 8, 500)]
    assert read_data == b"abcd"
    assert binding.writes == [(device, 0x82, b"payload", 7, 500)]
    assert written == 7


def test_d3xx_stream_pipe_read_uses_native_stream_read_api() -> None:
    binding = _FakeD3xxBinding()
    backend = D3xxBackend(binding)
    handle = backend.open(backend.iter_device_candidates()[0])
    device = _FakeD3xxInfo(0x0403601E, "N3DSXL.2", "NXL530228")

    handle.set_stream_pipe(0x82, 555008)
    read_data = handle.read_pipe(0x82, 555008, 500)

    assert binding.reads == []
    assert binding.stream_reads == [(device, 0x82, 555008, 500)]
    assert read_data == b"stream"


def test_pyd3xx_binding_missing_reports_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_module(module_name: str) -> object:
        _ = module_name
        raise ImportError

    monkeypatch.setattr(d3xx_backend, "import_module", missing_module)

    with pytest.raises(OptionalDependencyError):
        d3xx_backend.load_pyd3xx_binding()
