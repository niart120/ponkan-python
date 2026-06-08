"""FTD3 transport selection across libusb and D3XX backends."""

from typing import Literal, Protocol, cast

from py3dscapture.devices.n3dsxl_ftd3 import DeviceCandidate, N3DSXLDevice
from py3dscapture.errors import DeviceOpenError
from py3dscapture.transport.ftd3_pipe import FTD3_COMMAND_TIMEOUT_MS, Ftd3Pipe
from py3dscapture.transport.libusb_backend import LibusbBackend

BackendKind = Literal["libusb", "d3xx"]


class Ftd3Transport(Protocol):
    """Transport operations needed by FTD3/N3DSXL protocol code.

    The protocol is shared by libusb command-pipe transport and the optional
    native D3XX fallback.
    """

    backend_kind: BackendKind
    candidate: DeviceCandidate

    def close(self) -> None:
        """Close the transport.

        Implementations release any owned USB or D3XX handle resources.
        """
        ...

    def create_pipe(self) -> None:
        """Create the command pipe.

        Raises:
            Ftd3CommandError: The backend cannot create or emulate the command
                pipe.
        """
        ...

    def abort_pipe(self, pipe: int) -> None:
        """Abort one pipe.

        Args:
            pipe: Pipe or endpoint ID to abort.
        """
        ...

    def set_stream_pipe(self, pipe: int, length: int) -> None:
        """Configure a stream pipe.

        Args:
            pipe: Pipe or endpoint ID to configure.
            length: Stream transfer length in bytes.
        """
        ...

    def read_pipe(
        self,
        pipe: int,
        length: int,
        timeout_ms: int = FTD3_COMMAND_TIMEOUT_MS,
    ) -> bytes:
        """Read bytes from one pipe.

        Args:
            pipe: Pipe or endpoint ID to read.
            length: Maximum number of bytes to read.
            timeout_ms: Read timeout in milliseconds.

        Returns:
            Bytes returned by the backend.
        """
        ...

    def write_pipe(
        self,
        pipe: int,
        payload: bytes,
        timeout_ms: int = FTD3_COMMAND_TIMEOUT_MS,
    ) -> int:
        """Write bytes to one pipe.

        Args:
            pipe: Pipe or endpoint ID to write.
            payload: Bytes to transfer.
            timeout_ms: Write timeout in milliseconds.

        Returns:
            Number of bytes transferred.
        """
        ...

    def reconnect_after_drain(self) -> None:
        """Reconnect after drain if the backend requires it.

        D3XX closes and reopens to match cc3dsfs; libusb keeps the active
        session.
        """
        ...


class D3xxFallbackBackend(Protocol):
    """D3XX backend surface needed by fallback selection.

    The fallback is used only when libusb open fails with a driver/backend
    mismatch signal.
    """

    def iter_device_candidates(self) -> tuple[object, ...]:
        """Return D3XX candidates.

        Returns:
            Candidate objects accepted by the concrete D3XX backend.
        """
        ...

    def open(self, candidate: object) -> object:
        """Open a D3XX candidate.

        Args:
            candidate: Candidate object returned by ``iter_device_candidates``.

        Returns:
            Transport-compatible D3XX handle.
        """
        ...


class LibusbFtd3Transport:
    """FTD3 transport adapter over the existing libusb session.

    The adapter delegates command-pipe payload work to ``Ftd3Pipe`` and owns the
    underlying ``N3DSXLDevice`` session close.
    """

    backend_kind: BackendKind = "libusb"

    def __init__(self, session: N3DSXLDevice) -> None:
        """Create a transport adapter from an opened libusb session.

        Args:
            session: Open N3DSXL libusb session.
        """
        self.session = session
        self._pipe = Ftd3Pipe(session)

    @property
    def candidate(self) -> DeviceCandidate:
        """Return the accepted N3DSXL candidate for protocol metadata.

        Returns:
            Candidate associated with the underlying libusb session.
        """
        return self.session.candidate

    def close(self) -> None:
        """Close the underlying libusb session.

        This releases claimed interfaces and closes the USB handle.
        """
        self.session.close()

    def create_pipe(self) -> None:
        """Create the FTD3 command pipe through libusb command wrapper.

        Raises:
            Ftd3CommandError: The command write fails or transfers only a
                partial payload.
        """
        self._pipe.create_pipe()

    def abort_pipe(self, pipe: int) -> None:
        """Abort one FTD3 pipe through libusb command wrapper.

        Args:
            pipe: Pipe or endpoint ID to abort.
        """
        self._pipe.abort_pipe(pipe)

    def set_stream_pipe(self, pipe: int, length: int) -> None:
        """Set stream pipe through libusb command wrapper.

        Args:
            pipe: Pipe or endpoint ID to configure.
            length: Transfer length in bytes.
        """
        self._pipe.set_stream_pipe(pipe, length)

    def read_pipe(
        self,
        pipe: int,
        length: int,
        timeout_ms: int = FTD3_COMMAND_TIMEOUT_MS,
    ) -> bytes:
        """Read one FTD3 pipe through libusb command wrapper.

        Args:
            pipe: Pipe or endpoint ID to read.
            length: Maximum number of bytes to read.
            timeout_ms: Read timeout in milliseconds.

        Returns:
            Bytes read from the pipe.
        """
        return self._pipe.read_pipe(pipe, length, timeout_ms)

    def write_pipe(
        self,
        pipe: int,
        payload: bytes,
        timeout_ms: int = FTD3_COMMAND_TIMEOUT_MS,
    ) -> int:
        """Write one FTD3 pipe through libusb command wrapper.

        Args:
            pipe: Pipe or endpoint ID to write.
            payload: Bytes to transfer.
            timeout_ms: Write timeout in milliseconds.

        Returns:
            Number of bytes transferred.
        """
        return self._pipe.write_pipe(pipe, payload, timeout_ms)

    def reconnect_after_drain(self) -> None:
        """Keep libusb behavior unchanged after the initial drain.

        The libusb path keeps the current claimed session instead of closing and
        reopening like the D3XX fallback.
        """
        self._pipe.reconnect_after_drain()


def open_ftd3_transport(
    candidate: DeviceCandidate,
    libusb_backend: LibusbBackend,
    d3xx_backend: D3xxFallbackBackend,
) -> Ftd3Transport:
    """Open libusb first, then use D3XX only for driver/backend mismatch.

    Args:
        candidate: Accepted N3DSXL candidate to open.
        libusb_backend: Primary libusb backend.
        d3xx_backend: Fallback backend used when libusb reports a driver
            mismatch.

    Returns:
        Open transport compatible with ``N3DSXLProtocol``.

    Raises:
        DeviceOpenError: libusb open fails for reasons other than driver/backend
            mismatch, or D3XX fallback has no candidates.
    """
    try:
        return LibusbFtd3Transport(N3DSXLDevice.open(candidate, backend=libusb_backend))
    except DeviceOpenError as exc:
        if not _is_libusb_driver_mismatch(exc):
            raise
        d3xx_candidates = d3xx_backend.iter_device_candidates()
        if not d3xx_candidates:
            raise
        return cast("Ftd3Transport", d3xx_backend.open(d3xx_candidates[0]))


def _is_libusb_driver_mismatch(error: DeviceOpenError) -> bool:
    text = _error_chain_text(error)
    return "LIBUSB_ERROR_NOT_FOUND" in text or "LIBUSB_ERROR_NOT_SUPPORTED" in text


def _error_chain_text(error: BaseException) -> str:
    parts: list[str] = []
    current: BaseException | None = error
    while current is not None:
        parts.append(str(current))
        current = current.__cause__
    return " ".join(parts)
