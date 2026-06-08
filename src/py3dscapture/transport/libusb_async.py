"""Async transfer boundary for streaming."""

from typing import Protocol

from py3dscapture.streaming.buffers import RawFrameSlot


class AsyncTransferCallback(Protocol):
    """Callback invoked when one raw transfer completes.

    Backends must keep callback work small. The callback records metadata and
    must not perform decoding, blocking queue puts, or synchronous USB calls.
    """

    def __call__(
        self,
        slot_index: int,
        transferred: int,
        status: int,
        completed_ns: int,
    ) -> None:
        """Record completion metadata.

        Args:
            slot_index: Raw slot that completed.
            transferred: Number of bytes written into the slot.
            status: Backend status code, where zero means success.
            completed_ns: Monotonic completion timestamp.
        """
        ...


class AsyncTransferBackend(Protocol):
    """Minimal async transfer backend used by StreamingEngine.

    Implementations own transfer submission, cancellation, drain, and resource
    release. They write into preallocated ``RawFrameSlot`` buffers.
    """

    def submit_read(
        self,
        slot: RawFrameSlot,
        *,
        length: int,
        callback: AsyncTransferCallback,
    ) -> None:
        """Submit one async read into a preallocated slot.

        Args:
            slot: Checked-out raw slot whose buffer will receive bytes.
            length: Number of bytes to read into the slot.
            callback: Completion callback invoked when the read settles.

        Raises:
            ValueError: ``length`` does not fit in the slot buffer.
            RuntimeError: The backend has been released or is cancelling.
        """
        ...

    def cancel_all(self) -> None:
        """Cancel submitted transfers.

        Implementations should request cancellation for in-flight work without
        blocking indefinitely.
        """
        ...

    def drain(self) -> None:
        """Drain cancellation/completion callbacks.

        Returns only after submitted work has either completed or been
        cancelled according to backend semantics.
        """
        ...

    def release(self) -> None:
        """Release backend resources.

        Implementations should be idempotent and close any owned handles after
        cancellation and drain have completed.
        """
        ...


class LibusbAsyncBackend:
    """Placeholder for a hardware-backed libusb async implementation.

    The libusb async hardware path is intentionally gated by the local hardware
    work unit. Tests can use the protocol to inject fake async backends.
    """

    def submit_read(
        self,
        slot: RawFrameSlot,
        *,
        length: int,
        callback: AsyncTransferCallback,
    ) -> None:
        """Submit one async read into a preallocated slot.

        Args:
            slot: Checked-out raw slot whose buffer would receive bytes.
            length: Number of bytes requested.
            callback: Completion callback for a real implementation.

        Raises:
            NotImplementedError: The hardware implementation is not enabled.
        """
        _ = slot, length, callback
        raise NotImplementedError("hardware async backend is gated by local_013 hardware tests")

    def cancel_all(self) -> None:
        """Cancel submitted transfers.

        Raises:
            NotImplementedError: The hardware implementation is not enabled.
        """
        raise NotImplementedError("hardware async backend is gated by local_013 hardware tests")

    def drain(self) -> None:
        """Drain cancellation/completion callbacks.

        Raises:
            NotImplementedError: The hardware implementation is not enabled.
        """
        raise NotImplementedError("hardware async backend is gated by local_013 hardware tests")

    def release(self) -> None:
        """Release backend resources.

        Raises:
            NotImplementedError: The hardware implementation is not enabled.
        """
        raise NotImplementedError("hardware async backend is gated by local_013 hardware tests")
