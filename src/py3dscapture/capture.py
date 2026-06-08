"""Raw capture data model and fixture helpers."""

import json
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from py3dscapture.errors import DecodeError, TransferOverflow
from py3dscapture.image.frame import CaptureFrame


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
