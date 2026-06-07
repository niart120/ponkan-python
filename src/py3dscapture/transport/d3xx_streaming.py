"""D3XX-backed async transfer adapter for streaming."""

import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from threading import Event, Lock
from typing import Protocol

from py3dscapture.protocol.sizes import N3DSXL_BULK_IN_ENDPOINT
from py3dscapture.streaming.buffers import RawFrameSlot
from py3dscapture.transport.d3xx_backend import D3XX_DEFAULT_TIMEOUT_MS, D3xxBackendError
from py3dscapture.transport.libusb_async import AsyncTransferCallback


class D3xxAsyncBackendConfigError(ValueError):
    """Raised when D3XX async backend configuration is invalid."""


class D3xxAsyncBackendReleasedError(RuntimeError):
    """Raised when submitting to a released D3XX async backend."""


class D3xxAsyncBackendCancellingError(RuntimeError):
    """Raised when submitting while D3XX async backend cancellation is in progress."""


class D3xxStreamHandle(Protocol):
    """D3XX handle surface needed by the streaming adapter."""

    def read_pipe(self, pipe: int, length: int, timeout_ms: int) -> bytes:
        """Read one stream payload."""
        ...

    def close(self) -> None:
        """Close the D3XX handle."""
        ...


class D3xxAsyncBackend:
    """Adapt blocking D3XX stream reads to the StreamingEngine async boundary."""

    def __init__(
        self,
        handle: D3xxStreamHandle,
        *,
        pipe: int = N3DSXL_BULK_IN_ENDPOINT,
        timeout_ms: int = D3XX_DEFAULT_TIMEOUT_MS,
        max_workers: int = 1,
    ) -> None:
        """Create a sequential D3XX read worker backend."""
        if max_workers <= 0:
            raise D3xxAsyncBackendConfigError
        self._handle = handle
        self._pipe = pipe
        self._timeout_ms = timeout_ms
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="py3dscapture-d3xx-stream",
        )
        self._cancel_requested = Event()
        self._lock = Lock()
        self._futures: set[Future[None]] = set()
        self._released = False

    def submit_read(
        self,
        slot: RawFrameSlot,
        *,
        length: int,
        callback: AsyncTransferCallback,
    ) -> None:
        """Submit one read into a preallocated slot."""
        if length > len(slot.buffer):
            raise ValueError
        with self._lock:
            if self._released:
                raise D3xxAsyncBackendReleasedError
            if self._cancel_requested.is_set():
                raise D3xxAsyncBackendCancellingError
            future = self._executor.submit(self._read_into_slot, slot, length, callback)
            self._futures.add(future)
        future.add_done_callback(self._forget_future)

    def cancel_all(self) -> None:
        """Request cancellation and cancel pending worker jobs."""
        self._cancel_requested.set()
        with self._lock:
            futures = tuple(self._futures)
        for future in futures:
            future.cancel()

    def drain(self) -> None:
        """Wait for submitted worker jobs to settle."""
        while True:
            with self._lock:
                futures = tuple(self._futures)
            pending = tuple(future for future in futures if not future.done())
            if not pending:
                return
            wait(pending)

    def release(self) -> None:
        """Cancel workers, close the executor, and close the D3XX handle."""
        with self._lock:
            if self._released:
                return
            self._released = True
        self.cancel_all()
        self.drain()
        self._executor.shutdown(wait=True, cancel_futures=True)
        self._handle.close()

    def _read_into_slot(
        self,
        slot: RawFrameSlot,
        length: int,
        callback: AsyncTransferCallback,
    ) -> None:
        transferred = 0
        status = 0
        try:
            payload = self._handle.read_pipe(self._pipe, length, self._timeout_ms)
            payload = payload[:length]
            transferred = len(payload)
            slot.buffer[:transferred] = payload
        except D3xxBackendError as exc:
            status = 1 if exc.status is None else exc.status
        except (OSError, RuntimeError):
            status = 1
        completed_ns = time.monotonic_ns()
        if self._cancel_requested.is_set():
            return
        callback(slot.index, transferred, status, completed_ns)

    def _forget_future(self, future: Future[None]) -> None:
        with self._lock:
            self._futures.discard(future)
