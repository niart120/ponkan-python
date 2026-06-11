"""D3XX-backed async transfer adapter for streaming."""

import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from threading import Event, Lock
from typing import Protocol

from ponkan.protocol.sizes import N3DSXL_BULK_IN_ENDPOINT
from ponkan.streaming.buffers import RawFrameSlot
from ponkan.transport.d3xx_backend import D3XX_DEFAULT_TIMEOUT_MS, D3xxBackendError
from ponkan.transport.libusb_async import AsyncTransferCallback


class D3xxAsyncBackendConfigError(ValueError):
    """Raised when D3XX async backend configuration is invalid.

    Currently this is used for non-positive worker counts.
    """


class D3xxAsyncBackendReleasedError(RuntimeError):
    """Raised when submitting to a released D3XX async backend.

    Once released, the backend has closed its executor and handle.
    """


class D3xxAsyncBackendCancellingError(RuntimeError):
    """Raised when submitting while D3XX async backend cancellation is in progress.

    Submissions are rejected after cancellation starts so shutdown cannot race
    with new reads.
    """


class D3xxStreamHandle(Protocol):
    """D3XX handle surface needed by the streaming adapter.

    The handle is normally a ``D3xxHandle`` opened by the fallback backend, but
    tests may inject a smaller fake.
    """

    def read_pipe(self, pipe: int, length: int, timeout_ms: int) -> bytes:
        """Read one stream payload.

        Args:
            pipe: D3XX pipe ID to read.
            length: Maximum number of bytes to read.
            timeout_ms: Read timeout in milliseconds.

        Returns:
            Bytes returned by the handle.
        """
        ...

    def close(self) -> None:
        """Close the D3XX handle.

        Implementations release the native device handle and should make repeat
        calls harmless where possible.
        """
        ...


class D3xxAsyncBackend:
    """Adapt blocking D3XX stream reads to the StreamingEngine async boundary.

    Reads run in a worker executor and copy bytes into preallocated raw slots.
    Completion callbacks are invoked only after the worker read returns.
    """

    def __init__(
        self,
        handle: D3xxStreamHandle,
        *,
        pipe: int = N3DSXL_BULK_IN_ENDPOINT,
        timeout_ms: int = D3XX_DEFAULT_TIMEOUT_MS,
        max_workers: int = 1,
    ) -> None:
        """Create a sequential D3XX read worker backend.

        Args:
            handle: Open D3XX handle that owns pipe reads and close.
            pipe: D3XX pipe ID used for streaming reads.
            timeout_ms: Read timeout passed to the handle.
            max_workers: Number of read worker threads.

        Raises:
            D3xxAsyncBackendConfigError: ``max_workers`` is not positive.
        """
        if max_workers <= 0:
            raise D3xxAsyncBackendConfigError
        self._handle = handle
        self._pipe = pipe
        self._timeout_ms = timeout_ms
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="ponkan-d3xx-stream",
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
        """Submit one read into a preallocated slot.

        Args:
            slot: Checked-out raw slot whose buffer receives bytes.
            length: Maximum read length in bytes.
            callback: Completion callback invoked from the worker after read
                completion.

        Raises:
            ValueError: ``length`` is larger than the slot buffer.
            D3xxAsyncBackendReleasedError: The backend has already been
                released.
            D3xxAsyncBackendCancellingError: Cancellation is in progress.
        """
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
        """Request cancellation and cancel pending worker jobs.

        Running D3XX reads may still finish according to backend timeout
        behavior; completions after cancellation are ignored.
        """
        self._cancel_requested.set()
        with self._lock:
            futures = tuple(self._futures)
        for future in futures:
            future.cancel()

    def drain(self) -> None:
        """Wait for submitted worker jobs to settle.

        The method blocks until all submitted futures are done or cancelled.
        """
        while True:
            with self._lock:
                futures = tuple(self._futures)
            pending = tuple(future for future in futures if not future.done())
            if not pending:
                return
            wait(pending)

    def release(self) -> None:
        """Cancel workers, close the executor, and close the D3XX handle.

        The method is idempotent. It requests cancellation, drains worker jobs,
        shuts down the executor, and then closes the handle.
        """
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
        slot.backend_started_ns = time.monotonic_ns()
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
