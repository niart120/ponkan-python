import ctypes
import time

import pytest

from ponkan.streaming.buffers import RawFrameSlot
from ponkan.transport.d3xx_native import (
    FT_IO_INCOMPLETE,
    FT_IO_PENDING,
    FT_OK,
    FT_TIMEOUT,
    NativeOverlapped,
    NativeTransferResult,
)
from ponkan.transport.d3xx_native_streaming import (
    D3xxNativeFastPathBackend,
    D3xxNativeFastPathConfigError,
    D3xxNativeFastPathDrainTimeoutError,
)
from ponkan.transport.libusb_async import AsyncTransferCallback


class _FakeNativeApi:
    def __init__(self, payload: bytes = b"abcdef") -> None:
        self.payload = payload
        self.initialized = 0
        self.released = 0
        self.set_stream_pipe_calls: list[tuple[int, int]] = []
        self.reads: list[tuple[int, int]] = []
        self.abort_calls: list[int] = []
        self.get_result_calls = 0
        self.complete_after_incomplete = True
        self.never_complete = False
        self.result_status = FT_OK

    def initialize_overlapped(self, overlapped: NativeOverlapped) -> None:
        _ = overlapped
        self.initialized += 1

    def release_overlapped(self, overlapped: NativeOverlapped) -> None:
        _ = overlapped
        self.released += 1

    def set_stream_pipe(self, pipe: int, stream_size: int) -> None:
        self.set_stream_pipe_calls.append((pipe, stream_size))

    def abort_pipe(self, pipe: int) -> None:
        self.abort_calls.append(pipe)

    def read_pipe_ex(
        self,
        pipe: int,
        buffer: ctypes.Array[ctypes.c_char],
        length: int,
        overlapped: NativeOverlapped,
    ) -> NativeTransferResult:
        _ = overlapped
        self.reads.append((pipe, length))
        ctypes.memmove(buffer, self.payload, min(len(self.payload), length))
        return NativeTransferResult(FT_IO_PENDING, 0)

    def get_overlapped_result(
        self,
        overlapped: NativeOverlapped,
        *,
        wait: bool,
    ) -> NativeTransferResult:
        _ = overlapped, wait
        self.get_result_calls += 1
        if self.never_complete:
            return NativeTransferResult(FT_IO_INCOMPLETE, 0)
        if self.complete_after_incomplete and self.get_result_calls == 1:
            return NativeTransferResult(FT_IO_INCOMPLETE, 0)
        return NativeTransferResult(self.result_status, len(self.payload))


class _FakeHandle:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _CountingBufferFactory:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, size: int) -> ctypes.Array[ctypes.c_char]:
        self.calls += 1
        return ctypes.create_string_buffer(size)


def _slot(index: int = 0, size: int = 16) -> RawFrameSlot:
    return RawFrameSlot(index=index, buffer=bytearray(size))


def _wait_for(completions: list[tuple[int, int, int]], count: int = 1) -> None:
    deadline = time.monotonic() + 1.0
    while len(completions) < count and time.monotonic() < deadline:
        time.sleep(0.001)


def _recording_callback(completions: list[tuple[int, int, int]]) -> AsyncTransferCallback:
    def callback(
        slot_index: int,
        transferred: int,
        status: int,
        completed_ns: int,
    ) -> None:
        _ = completed_ns
        completions.append((slot_index, transferred, status))

    return callback


def test_native_fast_path_preallocates_and_completes_pending_read() -> None:
    api = _FakeNativeApi()
    handle = _FakeHandle()
    buffers = _CountingBufferFactory()
    backend = D3xxNativeFastPathBackend(
        handle,
        native_api=api,
        slot_count=2,
        read_size=16,
        poll_interval=0.001,
        buffer_factory=buffers,
    )
    completions: list[tuple[int, int, int]] = []
    slot = _slot()

    backend.submit_read(
        slot,
        length=8,
        callback=_recording_callback(completions),
    )
    _wait_for(completions)
    backend.drain()
    backend.release()

    assert buffers.calls == 2
    assert api.initialized == 2
    assert api.released == 2
    assert api.set_stream_pipe_calls == [(0x82, 16)]
    assert api.reads == [(0x82, 8)]
    assert bytes(slot.buffer[:6]) == b"abcdef"
    assert slot.backend_started_ns is not None
    assert completions == [(0, 6, 0)]
    assert handle.closed


def test_native_fast_path_reports_native_error_status() -> None:
    api = _FakeNativeApi()
    api.complete_after_incomplete = False
    api.result_status = FT_TIMEOUT
    handle = _FakeHandle()
    backend = D3xxNativeFastPathBackend(
        handle,
        native_api=api,
        slot_count=1,
        read_size=16,
        poll_interval=0.001,
    )
    completions: list[tuple[int, int, int]] = []

    backend.submit_read(
        _slot(),
        length=8,
        callback=_recording_callback(completions),
    )
    _wait_for(completions)
    backend.drain()
    backend.release()

    assert completions == [(0, 0, FT_TIMEOUT)]
    assert api.abort_calls


def test_native_fast_path_cancel_skips_late_callback_and_releases_resources() -> None:
    api = _FakeNativeApi()
    api.never_complete = True
    handle = _FakeHandle()
    backend = D3xxNativeFastPathBackend(
        handle,
        native_api=api,
        slot_count=1,
        read_size=16,
        poll_interval=0.001,
    )
    completions: list[tuple[int, int, int]] = []

    backend.submit_read(
        _slot(),
        length=8,
        callback=_recording_callback(completions),
    )
    while not api.reads:
        time.sleep(0.001)
    backend.cancel_all()
    api.never_complete = False
    backend.drain()
    backend.release()

    assert completions == []
    assert api.abort_calls
    assert api.released == 1
    assert handle.closed


def test_native_fast_path_drain_timeout_is_bounded() -> None:
    api = _FakeNativeApi()
    api.never_complete = True
    backend = D3xxNativeFastPathBackend(
        _FakeHandle(),
        native_api=api,
        slot_count=1,
        read_size=16,
        poll_interval=0.001,
        drain_timeout=0.01,
    )

    def callback(slot_index: int, transferred: int, status: int, completed_ns: int) -> None:
        _ = slot_index, transferred, status, completed_ns

    backend.submit_read(_slot(), length=8, callback=callback)

    with pytest.raises(D3xxNativeFastPathDrainTimeoutError):
        backend.drain()
    backend.cancel_all()
    api.never_complete = False
    backend.drain()
    backend.release()


def test_native_fast_path_rejects_invalid_config() -> None:
    with pytest.raises(D3xxNativeFastPathConfigError):
        D3xxNativeFastPathBackend(_FakeHandle(), native_api=_FakeNativeApi(), slot_count=0)
