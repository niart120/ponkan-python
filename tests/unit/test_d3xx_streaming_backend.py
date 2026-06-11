import threading
import time

import pytest

from ponkan.streaming.buffers import RawFrameSlot
from ponkan.transport.d3xx_backend import D3xxBackendError
from ponkan.transport.d3xx_streaming import (
    D3xxAsyncBackend,
    D3xxAsyncBackendConfigError,
)


class _FakeD3xxHandle:
    backend_kind = "d3xx"

    def __init__(self, payloads: list[bytes] | None = None) -> None:
        self.payloads = payloads or [b"frame"]
        self.reads: list[tuple[int, int, int]] = []
        self.closed = False
        self.raise_error: D3xxBackendError | None = None
        self.block_event: threading.Event | None = None

    def read_pipe(self, pipe: int, length: int, timeout_ms: int) -> bytes:
        self.reads.append((pipe, length, timeout_ms))
        if self.block_event is not None:
            self.block_event.wait(timeout=1.0)
        if self.raise_error is not None:
            raise self.raise_error
        return self.payloads.pop(0)

    def close(self) -> None:
        self.closed = True


def _slot(index: int = 0, size: int = 16) -> RawFrameSlot:
    return RawFrameSlot(index=index, buffer=bytearray(size))


def test_d3xx_async_backend_reads_into_slot_and_invokes_callback() -> None:
    handle = _FakeD3xxHandle([b"abcdef"])
    backend = D3xxAsyncBackend(handle, pipe=0x82, timeout_ms=250)
    slot = _slot()
    completions: list[tuple[int, int, int]] = []

    def callback(
        slot_index: int,
        transferred: int,
        status: int,
        completed_ns: int,
    ) -> None:
        _ = completed_ns
        completions.append((slot_index, transferred, status))

    backend.submit_read(
        slot,
        length=8,
        callback=callback,
    )
    backend.drain()
    backend.release()

    assert handle.reads == [(0x82, 8, 250)]
    assert bytes(slot.buffer[:6]) == b"abcdef"
    assert slot.backend_started_ns is not None
    assert completions == [(0, 6, 0)]
    assert handle.closed


def test_d3xx_async_backend_reports_d3xx_status_on_read_error() -> None:
    handle = _FakeD3xxHandle()
    handle.raise_error = D3xxBackendError("FT_ReadPipeEx", 32)
    backend = D3xxAsyncBackend(handle)
    completions: list[tuple[int, int, int]] = []

    def callback(
        slot_index: int,
        transferred: int,
        status: int,
        completed_ns: int,
    ) -> None:
        _ = completed_ns
        completions.append((slot_index, transferred, status))

    backend.submit_read(
        _slot(),
        length=8,
        callback=callback,
    )
    backend.drain()
    backend.release()

    assert completions == [(0, 0, 32)]


def test_cancel_all_skips_late_callback_and_release_closes_handle() -> None:
    handle = _FakeD3xxHandle([b"abcdef"])
    handle.block_event = threading.Event()
    backend = D3xxAsyncBackend(handle)
    completions: list[tuple[int, int, int]] = []

    def callback(
        slot_index: int,
        transferred: int,
        status: int,
        completed_ns: int,
    ) -> None:
        _ = completed_ns
        completions.append((slot_index, transferred, status))

    backend.submit_read(
        _slot(),
        length=8,
        callback=callback,
    )
    while not handle.reads:
        time.sleep(0.001)
    backend.cancel_all()
    handle.block_event.set()
    backend.drain()
    backend.release()

    assert completions == []
    assert handle.closed


def test_d3xx_async_backend_rejects_invalid_worker_count() -> None:
    with pytest.raises(D3xxAsyncBackendConfigError):
        D3xxAsyncBackend(_FakeD3xxHandle(), max_workers=0)
