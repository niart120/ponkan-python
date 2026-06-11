"""Raw capture models and high-level capture reader facade."""

import json
import time
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, cast, overload

from ponkan.errors import (
    DecodeError,
    DeviceNotFound,
    TransferOverflow,
    UnsupportedOperation,
)
from ponkan.image.frame import CaptureFrame, ColorSpace, RGB8Array
from ponkan.streaming.policies import DropPolicy
from ponkan.streaming.stats import StreamStats

if TYPE_CHECKING:
    from ponkan.protocol.n3dsxl import N3DSXLPipe, N3DSXLSessionIdentity
    from ponkan.transport.d3xx_streaming import D3xxStreamHandle
    from ponkan.transport.libusb_async import AsyncTransferBackend

CaptureSource = int | str
CaptureBackend = Literal["auto", "libusb", "d3xx", "d3xx-native"]

_VALID_BACKENDS = frozenset(("auto", "libusb", "d3xx", "d3xx-native"))
_VALID_COLORSPACES = frozenset(("RGB", "BGR"))
_VALID_DROP_POLICIES = frozenset(("drop_oldest", "drop_newest", "block"))
_COMPLETION_PROCESS_LIMIT = 8
_BACKEND_CONFIG_ERROR = "backend must be auto, libusb, d3xx, or d3xx-native"
_COLORSPACE_CONFIG_ERROR = "colorspace must be RGB or BGR"
_DROP_POLICY_CONFIG_ERROR = "drop_policy must be drop_oldest, drop_newest, or block"
_OUTPUT_QUEUE_SIZE_CONFIG_ERROR = "output_queue_size must be positive"
_POLL_INTERVAL_CONFIG_ERROR = "poll_interval must be positive"
_RAW_SLOTS_CONFIG_ERROR = "raw_slots must be positive"
_READ_TIMEOUT_CONFIG_ERROR = "read_timeout must be non-negative or None"


class _ReadTimeoutUnset:
    __slots__ = ()


_READ_TIMEOUT_UNSET = _ReadTimeoutUnset()


class CaptureOutput(StrEnum):
    """Screen layout returned by ``CaptureReader.read``."""

    TOP = "top"
    BOTTOM = "bottom"
    BOTH_VERTICAL = "both_vertical"


@dataclass(slots=True)
class CaptureConfig:
    """High-level capture reader configuration."""

    source: CaptureSource = 0
    model: Literal["new_3ds_xl"] = "new_3ds_xl"
    backend: CaptureBackend = "auto"
    mode_3d: bool = False
    output: CaptureOutput = CaptureOutput.BOTH_VERTICAL
    colorspace: ColorSpace = "RGB"
    raw_slots: int = 2
    output_queue_size: int = 2
    drop_policy: DropPolicy = "drop_oldest"
    poll_interval: float = 0.004
    read_timeout: float | None = 1.0
    collect_timing: bool = False


class CaptureReaderEngine(Protocol):
    """Streaming engine surface consumed by ``CaptureReader``."""

    def start(self) -> None:
        """Start frame acquisition."""
        ...

    def process_completed(self, *, limit: int | None = None) -> int:
        """Process pending backend completions."""
        ...

    def frames(self, *, max_frames: int | None = None) -> Iterator[CaptureFrame]:
        """Yield currently queued decoded frames."""
        ...

    def stop(self, timeout: float | None = None) -> None:
        """Stop acquisition and release owned backend resources."""
        ...

    def stats(self) -> StreamStats:
        """Return streaming counters."""
        ...


class _D3xxHandle(Protocol):
    def close(self) -> None:
        """Close the opened transport handle."""
        ...


class _D3xxBackend(Protocol):
    def iter_device_candidates(self) -> tuple[object, ...]:
        """Return accepted N3DSXL candidates visible through the backend."""
        ...

    def open(self, candidate: object) -> _D3xxHandle:
        """Open one accepted candidate."""
        ...


class _N3DSXLConnectProtocol(Protocol):
    def connect(self, *, mode_3d: bool) -> None:
        """Run the N3DSXL connect sequence."""
        ...


CaptureOpener = Callable[[CaptureConfig], CaptureReaderEngine]


@dataclass(slots=True)
class CaptureReader:
    """High-level reader that returns decoded N3DSXL frames or selected arrays."""

    engine: CaptureReaderEngine
    config: CaptureConfig = field(default_factory=CaptureConfig)
    _started: bool = False
    _closed: bool = False

    def read(
        self,
        *,
        output: CaptureOutput | str | None = None,
        colorspace: ColorSpace | None = None,
        timeout: float | None = None,
    ) -> RGB8Array | None:
        """Return the next selected screen layout as an RGB or BGR ndarray.

        Args:
            output: Screen layout to return. ``None`` uses reader config.
            colorspace: Channel order to return. ``None`` uses reader config.
            timeout: Optional timeout override in seconds. ``None`` uses reader
                config.

        Returns:
            A copied ``uint8`` ndarray, or ``None`` when no frame arrives before
            the effective timeout.
        """
        frame = self.read_frame(timeout=timeout)
        if frame is None:
            return None
        selected_output = _coerce_output(self.config.output if output is None else output)
        selected_colorspace = self.config.colorspace if colorspace is None else colorspace
        _validate_colorspace(selected_colorspace)
        if selected_output == CaptureOutput.TOP:
            return frame.to_ndarray("top", selected_colorspace)
        if selected_output == CaptureOutput.BOTTOM:
            return frame.to_ndarray("bottom", selected_colorspace)
        mosaic = frame.to_mosaic(gap=0)
        if selected_colorspace == "RGB":
            return mosaic
        return mosaic[..., ::-1].copy()

    def read_frame(self, *, timeout: float | None = None) -> CaptureFrame | None:
        """Return the latest decoded ``CaptureFrame`` available before timeout.

        Args:
            timeout: Optional timeout override in seconds. ``None`` uses reader
                config.

        Returns:
            Latest decoded frame from the currently queued frames, or ``None``
            on timeout or after close.
        """
        if self._closed:
            return None
        self._ensure_started()
        timeout_seconds = self.config.read_timeout if timeout is None else timeout
        deadline = None if timeout_seconds is None else time.monotonic() + timeout_seconds
        while True:
            self.engine.process_completed(limit=_COMPLETION_PROCESS_LIMIT)
            latest = self._latest_available_frame()
            if latest is not None:
                return latest
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                time.sleep(min(self.config.poll_interval, remaining))
            else:
                time.sleep(self.config.poll_interval)

    def stats(self) -> StreamStats:
        """Return a snapshot of streaming counters."""
        return self.engine.stats()

    def close(self) -> None:
        """Stop acquisition and release resources once."""
        if self._closed:
            return
        self._closed = True
        self.engine.stop()

    def __enter__(self) -> "CaptureReader":
        """Return this reader for context-manager use."""
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        """Close the reader when leaving a context manager."""
        _ = exc_type, exc, traceback
        self.close()

    def _ensure_started(self) -> None:
        if self._started:
            return
        self.engine.start()
        self._started = True

    def _latest_available_frame(self) -> CaptureFrame | None:
        latest: CaptureFrame | None = None
        for frame in self.engine.frames():
            latest = frame
        return latest


@overload
def open_capture(
    source: CaptureSource = 0,
    *,
    config: CaptureConfig | None = None,
    backend: CaptureBackend | None = None,
    output: CaptureOutput | str | None = None,
    colorspace: ColorSpace | None = None,
    read_timeout: float | None = None,
    _opener: "CaptureOpener | None" = None,
) -> CaptureReader: ...


@overload
def open_capture(
    source: CaptureSource = 0,
    *,
    config: CaptureConfig | None = None,
    backend: CaptureBackend | None = None,
    output: CaptureOutput | str | None = None,
    colorspace: ColorSpace | None = None,
    _opener: "CaptureOpener | None" = None,
) -> CaptureReader: ...


def open_capture(
    source: CaptureSource = 0,
    *,
    config: CaptureConfig | None = None,
    backend: CaptureBackend | None = None,
    output: CaptureOutput | str | None = None,
    colorspace: ColorSpace | None = None,
    read_timeout: float | None | _ReadTimeoutUnset = _READ_TIMEOUT_UNSET,
    _opener: "CaptureOpener | None" = None,
) -> CaptureReader:
    """Open a high-level N3DSXL capture reader.

    Args:
        source: Initial source selector. ``0`` and ``"new_3ds_xl"`` are
            supported by the MVP.
        config: Optional base configuration.
        backend: Optional backend preference override.
        output: Optional default output layout override.
        colorspace: Optional default output color-space override.
        read_timeout: Optional default read timeout override.
        _opener: Internal test injection. Production callers should omit it.

    Returns:
        Open high-level reader.
    """
    resolved = _resolve_config(
        source=source,
        config=config,
        backend=backend,
        output=output,
        colorspace=colorspace,
        read_timeout=read_timeout,
    )
    opener = _open_hardware_engine if _opener is None else _opener
    return CaptureReader(opener(resolved), config=resolved)


def _resolve_config(
    *,
    source: CaptureSource,
    config: CaptureConfig | None,
    backend: CaptureBackend | None,
    output: CaptureOutput | str | None,
    colorspace: ColorSpace | None,
    read_timeout: float | None | _ReadTimeoutUnset,
) -> CaptureConfig:
    resolved = config or CaptureConfig(source=source)
    if config is not None and source != 0:
        resolved = replace(resolved, source=source)
    if backend is not None:
        resolved = replace(resolved, backend=backend)
    if output is not None:
        resolved = replace(resolved, output=_coerce_output(output))
    if colorspace is not None:
        resolved = replace(resolved, colorspace=colorspace)
    if not isinstance(read_timeout, _ReadTimeoutUnset):
        resolved = replace(resolved, read_timeout=read_timeout)
    _validate_config(resolved)
    return resolved


def _validate_config(config: CaptureConfig) -> None:
    if config.source not in (0, "new_3ds_xl"):
        raise UnsupportedOperation
    if config.model != "new_3ds_xl":
        raise UnsupportedOperation
    if config.backend not in _VALID_BACKENDS:
        raise ValueError(_BACKEND_CONFIG_ERROR)
    if config.mode_3d:
        raise UnsupportedOperation
    _coerce_output(config.output)
    _validate_colorspace(config.colorspace)
    if config.raw_slots <= 0:
        raise ValueError(_RAW_SLOTS_CONFIG_ERROR)
    if config.output_queue_size <= 0:
        raise ValueError(_OUTPUT_QUEUE_SIZE_CONFIG_ERROR)
    if config.drop_policy not in _VALID_DROP_POLICIES:
        raise ValueError(_DROP_POLICY_CONFIG_ERROR)
    if config.poll_interval <= 0:
        raise ValueError(_POLL_INTERVAL_CONFIG_ERROR)
    if config.read_timeout is not None and config.read_timeout < 0:
        raise ValueError(_READ_TIMEOUT_CONFIG_ERROR)


def _coerce_output(output: CaptureOutput | str) -> CaptureOutput:
    if isinstance(output, CaptureOutput):
        return output
    return CaptureOutput(output)


def _validate_colorspace(colorspace: str) -> None:
    if colorspace not in _VALID_COLORSPACES:
        raise ValueError(_COLORSPACE_CONFIG_ERROR)


def _open_hardware_engine(config: CaptureConfig) -> CaptureReaderEngine:
    if config.backend == "libusb":
        raise UnsupportedOperation
    native = config.backend == "d3xx-native"
    return _open_d3xx_engine(config, native=native)


def _open_d3xx_engine(config: CaptureConfig, *, native: bool) -> CaptureReaderEngine:
    backend = _new_d3xx_backend()
    candidates = backend.iter_device_candidates()
    if not candidates:
        raise DeviceNotFound
    d3xx_candidate = candidates[0]
    handle = backend.open(d3xx_candidate)
    try:
        protocol = _new_n3dsxl_protocol(handle)
        protocol.connect(mode_3d=False)
        async_backend = (
            _new_d3xx_native_backend(handle, config) if native else _new_d3xx_backend_async(handle)
        )
        return _new_streaming_engine(async_backend, config)
    except Exception:
        handle.close()
        raise


def _new_d3xx_backend() -> _D3xxBackend:
    from ponkan.transport.d3xx_backend import D3xxBackend  # noqa: PLC0415

    return D3xxBackend()


def _new_n3dsxl_protocol(handle: _D3xxHandle) -> _N3DSXLConnectProtocol:
    from ponkan.protocol.n3dsxl import N3DSXLProtocol  # noqa: PLC0415

    return N3DSXLProtocol(
        cast("N3DSXLSessionIdentity", handle),
        cast("N3DSXLPipe", handle),
    )


def _new_d3xx_backend_async(handle: _D3xxHandle) -> object:
    from ponkan.transport.d3xx_streaming import D3xxAsyncBackend  # noqa: PLC0415

    return D3xxAsyncBackend(cast("D3xxStreamHandle", handle))


def _new_d3xx_native_backend(handle: _D3xxHandle, config: CaptureConfig) -> object:
    from ponkan.transport.d3xx_native_streaming import (  # noqa: PLC0415
        D3xxNativeFastPathBackend,
    )

    return D3xxNativeFastPathBackend(handle, slot_count=config.raw_slots)


def _new_streaming_engine(async_backend: object, config: CaptureConfig) -> CaptureReaderEngine:
    from ponkan.streaming.engine import StreamingEngine  # noqa: PLC0415

    return StreamingEngine(
        cast("AsyncTransferBackend", async_backend),
        raw_slots=config.raw_slots,
        output_queue_size=config.output_queue_size,
        drop_policy=config.drop_policy,
        collect_timing=config.collect_timing,
    )


@dataclass(slots=True)
class RawCapture:
    """Raw transfer payload and metadata for one capture frame.

    Attributes:
        model: Capture target model that produced the payload.
        mode_3d: Whether the transfer was captured in 3D mode.
        payload: Raw bytes returned by the transport. Only the first
            ``transferred`` bytes are considered part of the transfer.
        transferred: Number of bytes reported by the transport.
        video_size: Number of RGB8 video bytes expected at the start of the
            payload.
        capture_size: Maximum accepted transfer size for the selected mode.
        timestamp_ns: Optional monotonic timestamp associated with completion.
        sequence: Optional stream sequence number.
        metadata: Additional JSON-serializable capture metadata.
    """

    model: Literal["new_3ds_xl"]
    mode_3d: bool
    payload: bytes
    transferred: int
    video_size: int
    capture_size: int
    timestamp_ns: int | None
    sequence: int | None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate transfer bounds and payload length.

        Raises:
            DecodeError: The transfer is too short for the video region, or the
                payload does not contain the reported transfer length.
            TransferOverflow: The transport reported more bytes than the
                selected capture mode accepts.
        """
        if self.transferred < self.video_size:
            raise DecodeError
        if self.transferred > self.capture_size:
            raise TransferOverflow
        if len(self.payload) < self.transferred:
            raise DecodeError

    def video_region(self) -> bytes:
        """Return the raw RGB8 video region.

        Returns:
            The leading ``video_size`` bytes from ``payload``. Audio, unused,
            and error-buffer regions are intentionally excluded.
        """
        return self.payload[: self.video_size]

    def to_metadata(self) -> dict[str, object]:
        """Return JSON-serializable metadata.

        Existing metadata is copied before standard capture fields are added.
        ``decoder_version`` and ``manual_visual_status`` are populated with
        default values when the caller did not provide them.

        Returns:
            A JSON-serializable dictionary suitable for sidecar artifact files.
        """
        data = dict(self.metadata)
        data.update(
            {
                "model": self.model,
                "mode_3d": self.mode_3d,
                "transferred": self.transferred,
                "video_size": self.video_size,
                "capture_size": self.capture_size,
                "sequence": self.sequence,
                "timestamp_ns": self.timestamp_ns,
            }
        )
        data.setdefault("decoder_version", None)
        data.setdefault("manual_visual_status", "pending")
        return data


def save_raw_capture(
    capture: RawCapture,
    out_path: Path,
    *,
    force: bool = False,
) -> tuple[Path, Path]:
    """Save raw bytes and JSON metadata using the same stem.

    The binary file is written to ``out_path``. The metadata file is written
    next to it with the same stem and a ``.json`` suffix.

    Args:
        capture: Raw capture whose payload contains at least ``transferred``
            bytes.
        out_path: Destination path for the raw binary payload.
        force: Overwrite an existing binary or metadata file when true.

    Returns:
        ``(bin_path, metadata_path)`` for the files written by this call.

    Raises:
        FileExistsError: Either destination exists and ``force`` is false.
    """
    bin_path = out_path
    metadata_path = out_path.with_suffix(".json")
    if not force and (bin_path.exists() or metadata_path.exists()):
        raise FileExistsError

    bin_path.parent.mkdir(parents=True, exist_ok=True)
    bin_path.write_bytes(capture.payload[: capture.transferred])
    metadata_path.write_text(
        json.dumps(capture.to_metadata(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return bin_path, metadata_path


class FrameEngine(Protocol):
    """Small streaming engine surface exposed by CaptureSession.

    Implementations may be real hardware streaming engines or test doubles.
    They are expected to yield already decoded ``CaptureFrame`` objects.
    """

    def frames(self, *, max_frames: int | None = None) -> Iterator[CaptureFrame]:
        """Yield decoded frames.

        Args:
            max_frames: Maximum number of frames to yield, or ``None`` to yield
                until the engine has no currently available frame.

        Yields:
            Decoded capture frames from the engine.
        """
        ...

    def frames_async(self, *, max_frames: int | None = None) -> AsyncIterator[CaptureFrame]:
        """Yield decoded frames asynchronously.

        Args:
            max_frames: Maximum number of frames to yield, or ``None`` to yield
                until the engine has no currently available frame.

        Yields:
            Decoded capture frames from the engine.
        """
        ...


@dataclass(slots=True)
class CaptureSession:
    """Public capture session facade.

    Attributes:
        engine: Streaming engine or compatible test double that owns frame
            production.
    """

    engine: FrameEngine

    def frames(self, *, max_frames: int | None = None) -> Iterator[CaptureFrame]:
        """Yield decoded frames from the underlying engine.

        Args:
            max_frames: Maximum number of frames to yield, or ``None`` to yield
                all currently available frames.

        Yields:
            Decoded capture frames.
        """
        yield from self.engine.frames(max_frames=max_frames)

    async def frames_async(self, *, max_frames: int | None = None) -> AsyncIterator[CaptureFrame]:
        """Yield decoded frames asynchronously from the underlying engine.

        Args:
            max_frames: Maximum number of frames to yield, or ``None`` to yield
                all currently available frames.

        Yields:
            Decoded capture frames.
        """
        async for frame in self.engine.frames_async(max_frames=max_frames):
            yield frame
