"""Native D3XX fast-path async transfer adapter."""

import ctypes
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, Protocol, cast

from py3dscapture.protocol.sizes import N3DSXL_BULK_IN_ENDPOINT, capture_size
from py3dscapture.streaming.buffers import RawFrameSlot
from py3dscapture.transport.d3xx_backend import D3XX_DEFAULT_TIMEOUT_MS, D3xxBackendError
from py3dscapture.transport.d3xx_native import (
    FT_IO_INCOMPLETE,
    FT_IO_PENDING,
    FT_OK,
    D3xxNativeApi,
    NativeOverlapped,
    NativeTransferResult,
)
from py3dscapture.transport.libusb_async import AsyncTransferCallback

if TYPE_CHECKING:
    from py3dscapture.transport.d3xx_native import D3xxNativeHandleProvider

NativeBufferFactory = Callable[[int], ctypes.Array[ctypes.c_char]]


class D3xxNativeFastPathConfigError(ValueError):
    """Raised when native fast-path backend configuration is invalid."""


class D3xxNativeFastPathReleasedError(RuntimeError):
    """Raised when submitting to a released native fast-path backend."""


class D3xxNativeFastPathCancellingError(RuntimeError):
    """Raised when submitting while native fast-path cancellation is active."""


class D3xxNativeFastPathDrainTimeoutError(RuntimeError):
    """Raised when pending native transfers do not drain within the limit."""


class D3xxNativeFastPathSlotBusyError(RuntimeError):
    """Raised when a raw slot is submitted while already in flight."""


class D3xxNativeHandle(Protocol):
    """Handle surface owned by the native fast-path backend."""

    def close(self) -> None:
        """Close the underlying D3XX handle."""
        ...


class D3xxNativeApiProtocol(Protocol):
    """Native API operations required by the fast-path backend."""

    def initialize_overlapped(self, overlapped: NativeOverlapped) -> None:
        """Initialize one overlapped object."""
        ...

    def release_overlapped(self, overlapped: NativeOverlapped) -> None:
        """Release one overlapped object."""
        ...

    def set_stream_pipe(self, pipe: int, stream_size: int) -> None:
        """Configure fixed-size stream transfers."""
        ...

    def abort_pipe(self, pipe: int) -> None:
        """Abort pending transfers on one pipe."""
        ...

    def read_pipe_ex(
        self,
        pipe: int,
        buffer: ctypes.Array[ctypes.c_char],
        length: int,
        overlapped: NativeOverlapped,
    ) -> NativeTransferResult:
        """Submit a native stream read."""
        ...

    def get_overlapped_result(
        self,
        overlapped: NativeOverlapped,
        *,
        wait: bool,
    ) -> NativeTransferResult:
        """Return pending native read status."""
        ...


@dataclass(slots=True)
class NativeReadSlot:
    """Backend-owned native buffer and overlapped state for one raw slot."""

    slot_index: int
    buffer: ctypes.Array[ctypes.c_char]
    overlapped: NativeOverlapped
    raw_slot: RawFrameSlot | None = None
    callback: AsyncTransferCallback | None = None
    length: int = 0
    in_flight: bool = False
    backend_started_ns: int | None = None


class D3xxNativeFastPathBackend:
    """Adapt native D3XX overlapped reads to the StreamingEngine boundary."""

    def __init__(
        self,
        handle: D3xxNativeHandle,
        *,
        native_api: D3xxNativeApiProtocol | None = None,
        pipe: int = N3DSXL_BULK_IN_ENDPOINT,
        slot_count: int = 2,
        read_size: int | None = None,
        timeout_ms: int = D3XX_DEFAULT_TIMEOUT_MS,
        poll_interval: float = 0.001,
        drain_timeout: float = 2.0,
        buffer_factory: NativeBufferFactory = ctypes.create_string_buffer,
    ) -> None:
        """Create a D3XX native fast-path streaming backend.

        Args:
            handle: Open D3XX handle that will be closed on release.
            native_api: Optional native API wrapper. When omitted, it is built
                from the PyD3XX-backed handle provider.
            pipe: Read pipe ID.
            slot_count: Number of preallocated native slots.
            read_size: Native buffer size. Defaults to the 2D N3DSXL capture
                transfer size.
            timeout_ms: Reserved to match D3XX backend configuration; native
                overlapped reads use pipe timeout state configured elsewhere.
            poll_interval: Completion poll interval in seconds.
            drain_timeout: Maximum seconds to wait for cancellation drain.
            buffer_factory: Test hook for native buffer allocation.

        Raises:
            D3xxNativeFastPathConfigError: Configuration values are invalid.
        """
        _ = timeout_ms
        if slot_count <= 0 or (read_size is not None and read_size <= 0):
            raise D3xxNativeFastPathConfigError
        if poll_interval <= 0 or drain_timeout <= 0:
            raise D3xxNativeFastPathConfigError
        self._handle = handle
        self._native_api = native_api or D3xxNativeApi.from_pyd3xx_handle(
            cast("D3xxNativeHandleProvider", handle)
        )
        self._pipe = pipe
        self._slot_count = slot_count
        self._read_size = read_size or capture_size(mode_3d=False)
        self._poll_interval = poll_interval
        self._drain_timeout = drain_timeout
        self._lock = Lock()
        self._wake = Event()
        self._cancel_requested = Event()
        self._released = False
        self._slots = tuple(
            self._create_native_slot(index, buffer_factory) for index in range(slot_count)
        )
        self._native_api.set_stream_pipe(self._pipe, self._read_size)
        self._pump = Thread(
            target=self._completion_pump,
            name="py3dscapture-d3xx-native-stream",
        )
        self._pump.start()

    def submit_read(
        self,
        slot: RawFrameSlot,
        *,
        length: int,
        callback: AsyncTransferCallback,
    ) -> None:
        """Submit one native overlapped read into a preallocated native slot."""
        if length > len(slot.buffer) or length > self._read_size:
            raise ValueError
        native_slot = self._slot_for_raw(slot)
        with self._lock:
            if self._released:
                raise D3xxNativeFastPathReleasedError
            if self._cancel_requested.is_set():
                raise D3xxNativeFastPathCancellingError
            if native_slot.in_flight:
                raise D3xxNativeFastPathSlotBusyError
            native_slot.raw_slot = slot
            native_slot.callback = callback
            native_slot.length = length
            native_slot.backend_started_ns = time.monotonic_ns()
            native_slot.in_flight = True
            slot.backend_started_ns = native_slot.backend_started_ns
        result = self._native_api.read_pipe_ex(
            self._pipe,
            native_slot.buffer,
            length,
            native_slot.overlapped,
        )
        if result.status == FT_IO_PENDING:
            self._wake.set()
            return
        self._settle_slot(native_slot, result)

    def cancel_all(self) -> None:
        """Request cancellation and abort the native read pipe."""
        self._cancel_requested.set()
        self._native_api.abort_pipe(self._pipe)
        self._wake.set()

    def drain(self) -> None:
        """Wait for all in-flight native reads to settle with a bounded timeout."""
        deadline = time.monotonic() + self._drain_timeout
        while self._has_in_flight():
            if time.monotonic() >= deadline:
                raise D3xxNativeFastPathDrainTimeoutError
            self._wake.set()
            time.sleep(min(self._poll_interval, 0.01))

    def release(self) -> None:
        """Cancel pending reads, release native resources, and close the handle."""
        with self._lock:
            if self._released:
                return
            self._released = True
        self.cancel_all()
        self.drain()
        self._wake.set()
        self._pump.join(timeout=self._drain_timeout)
        for native_slot in self._slots:
            self._native_api.release_overlapped(native_slot.overlapped)
        self._handle.close()

    def _create_native_slot(
        self,
        index: int,
        buffer_factory: NativeBufferFactory,
    ) -> NativeReadSlot:
        overlapped = NativeOverlapped()
        self._native_api.initialize_overlapped(overlapped)
        return NativeReadSlot(
            slot_index=index,
            buffer=buffer_factory(self._read_size),
            overlapped=overlapped,
        )

    def _completion_pump(self) -> None:
        while True:
            if self._released and not self._has_in_flight():
                return
            did_settle = False
            for native_slot in self._in_flight_slots():
                result = self._native_api.get_overlapped_result(
                    native_slot.overlapped,
                    wait=False,
                )
                if result.status == FT_IO_INCOMPLETE:
                    continue
                self._settle_slot(native_slot, result)
                did_settle = True
            if did_settle:
                continue
            self._wake.wait(self._poll_interval)
            self._wake.clear()

    def _settle_slot(self, native_slot: NativeReadSlot, result: NativeTransferResult) -> None:
        completed_ns = time.monotonic_ns()
        callback: AsyncTransferCallback | None
        raw_slot: RawFrameSlot | None
        with self._lock:
            if not native_slot.in_flight:
                return
            native_slot.in_flight = False
            callback = native_slot.callback
            raw_slot = native_slot.raw_slot
            native_slot.callback = None
            native_slot.raw_slot = None
        if raw_slot is None or callback is None:
            return
        if self._cancel_requested.is_set():
            return
        transferred = min(result.transferred, native_slot.length)
        status = result.status
        if status == FT_OK:
            raw_slot.buffer[:transferred] = native_slot.buffer.raw[:transferred]
        elif status != FT_IO_PENDING:
            with suppress(D3xxBackendError):
                self._native_api.abort_pipe(self._pipe)
        callback(raw_slot.index, transferred if status == FT_OK else 0, status, completed_ns)

    def _slot_for_raw(self, slot: RawFrameSlot) -> NativeReadSlot:
        if slot.index < 0 or slot.index >= self._slot_count:
            raise IndexError
        return self._slots[slot.index]

    def _in_flight_slots(self) -> tuple[NativeReadSlot, ...]:
        with self._lock:
            return tuple(slot for slot in self._slots if slot.in_flight)

    def _has_in_flight(self) -> bool:
        with self._lock:
            return any(slot.in_flight for slot in self._slots)
