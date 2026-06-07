"""FTD3 transport selection across libusb and D3XX backends."""

from typing import Literal, Protocol, cast

from py3dscapture.devices.n3dsxl_ftd3 import DeviceCandidate, N3DSXLDevice
from py3dscapture.errors import DeviceOpenError
from py3dscapture.transport.ftd3_pipe import FTD3_COMMAND_TIMEOUT_MS, Ftd3Pipe
from py3dscapture.transport.libusb_backend import LibusbBackend

BackendKind = Literal["libusb", "d3xx"]


class Ftd3Transport(Protocol):
    """Transport operations needed by FTD3/N3DSXL protocol code."""

    backend_kind: BackendKind
    candidate: DeviceCandidate

    def close(self) -> None:
        """Close the transport."""
        ...

    def create_pipe(self) -> None:
        """Create the command pipe."""
        ...

    def abort_pipe(self, pipe: int) -> None:
        """Abort one pipe."""
        ...

    def set_stream_pipe(self, pipe: int, length: int) -> None:
        """Configure a stream pipe."""
        ...

    def read_pipe(
        self,
        pipe: int,
        length: int,
        timeout_ms: int = FTD3_COMMAND_TIMEOUT_MS,
    ) -> bytes:
        """Read bytes from one pipe."""
        ...

    def write_pipe(
        self,
        pipe: int,
        payload: bytes,
        timeout_ms: int = FTD3_COMMAND_TIMEOUT_MS,
    ) -> int:
        """Write bytes to one pipe."""
        ...

    def reconnect_after_drain(self) -> None:
        """Reconnect after drain if the backend requires it."""
        ...


class D3xxFallbackBackend(Protocol):
    """D3XX backend surface needed by fallback selection."""

    def iter_device_candidates(self) -> tuple[object, ...]:
        """Return D3XX candidates."""
        ...

    def open(self, candidate: object) -> object:
        """Open a D3XX candidate."""
        ...


class LibusbFtd3Transport:
    """FTD3 transport adapter over the existing libusb session."""

    backend_kind: BackendKind = "libusb"

    def __init__(self, session: N3DSXLDevice) -> None:
        """Create a transport adapter from an opened libusb session."""
        self.session = session
        self._pipe = Ftd3Pipe(session)

    @property
    def candidate(self) -> DeviceCandidate:
        """Return the accepted N3DSXL candidate for protocol metadata."""
        return self.session.candidate

    def close(self) -> None:
        """Close the underlying libusb session."""
        self.session.close()

    def create_pipe(self) -> None:
        """Create the FTD3 command pipe through libusb command wrapper."""
        self._pipe.create_pipe()

    def abort_pipe(self, pipe: int) -> None:
        """Abort one FTD3 pipe through libusb command wrapper."""
        self._pipe.abort_pipe(pipe)

    def set_stream_pipe(self, pipe: int, length: int) -> None:
        """Set stream pipe through libusb command wrapper."""
        self._pipe.set_stream_pipe(pipe, length)

    def read_pipe(
        self,
        pipe: int,
        length: int,
        timeout_ms: int = FTD3_COMMAND_TIMEOUT_MS,
    ) -> bytes:
        """Read one FTD3 pipe through libusb command wrapper."""
        return self._pipe.read_pipe(pipe, length, timeout_ms)

    def write_pipe(
        self,
        pipe: int,
        payload: bytes,
        timeout_ms: int = FTD3_COMMAND_TIMEOUT_MS,
    ) -> int:
        """Write one FTD3 pipe through libusb command wrapper."""
        return self._pipe.write_pipe(pipe, payload, timeout_ms)

    def reconnect_after_drain(self) -> None:
        """Keep libusb behavior unchanged after the initial drain."""
        self._pipe.reconnect_after_drain()


def open_ftd3_transport(
    candidate: DeviceCandidate,
    libusb_backend: LibusbBackend,
    d3xx_backend: D3xxFallbackBackend,
) -> Ftd3Transport:
    """Open libusb first, then use D3XX only for driver/backend mismatch."""
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
