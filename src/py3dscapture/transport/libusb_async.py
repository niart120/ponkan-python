"""Async transfer boundary for streaming."""

from typing import Protocol

from py3dscapture.streaming.buffers import RawFrameSlot


class AsyncTransferCallback(Protocol):
    """Callback invoked when one raw transfer completes."""

    def __call__(
        self,
        slot_index: int,
        transferred: int,
        status: int,
        completed_ns: int,
    ) -> None:
        """Record completion metadata."""
        ...


class AsyncTransferBackend(Protocol):
    """Minimal async transfer backend used by StreamingEngine."""

    def submit_read(
        self,
        slot: RawFrameSlot,
        *,
        length: int,
        callback: AsyncTransferCallback,
    ) -> None:
        """Submit one async read into a preallocated slot."""
        ...

    def cancel_all(self) -> None:
        """Cancel submitted transfers."""
        ...

    def drain(self) -> None:
        """Drain cancellation/completion callbacks."""
        ...

    def release(self) -> None:
        """Release backend resources."""
        ...


class LibusbAsyncBackend:
    """Placeholder for a hardware-backed libusb async implementation."""

    def submit_read(
        self,
        slot: RawFrameSlot,
        *,
        length: int,
        callback: AsyncTransferCallback,
    ) -> None:
        """Submit one async read into a preallocated slot."""
        _ = slot, length, callback
        raise NotImplementedError("hardware async backend is gated by local_013 hardware tests")

    def cancel_all(self) -> None:
        """Cancel submitted transfers."""
        raise NotImplementedError("hardware async backend is gated by local_013 hardware tests")

    def drain(self) -> None:
        """Drain cancellation/completion callbacks."""
        raise NotImplementedError("hardware async backend is gated by local_013 hardware tests")

    def release(self) -> None:
        """Release backend resources."""
        raise NotImplementedError("hardware async backend is gated by local_013 hardware tests")
