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
    """Raw transfer payload and metadata for one capture frame."""

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
        """Validate transfer bounds and payload length."""
        if self.transferred < self.video_size:
            raise DecodeError
        if self.transferred > self.capture_size:
            raise TransferOverflow
        if len(self.payload) < self.transferred:
            raise DecodeError

    def video_region(self) -> bytes:
        """Return the raw RGB8 video region."""
        return self.payload[: self.video_size]

    def to_metadata(self) -> dict[str, object]:
        """Return JSON-serializable metadata."""
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
    """Save raw bytes and JSON metadata using the same stem."""
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
    """Small streaming engine surface exposed by CaptureSession."""

    def frames(self, *, max_frames: int | None = None) -> Iterator[CaptureFrame]:
        """Yield decoded frames."""
        ...

    def frames_async(self, *, max_frames: int | None = None) -> AsyncIterator[CaptureFrame]:
        """Yield decoded frames asynchronously."""
        ...


@dataclass(slots=True)
class CaptureSession:
    """Public capture session facade."""

    engine: FrameEngine

    def frames(self, *, max_frames: int | None = None) -> Iterator[CaptureFrame]:
        """Yield decoded frames from the underlying engine."""
        yield from self.engine.frames(max_frames=max_frames)

    async def frames_async(self, *, max_frames: int | None = None) -> AsyncIterator[CaptureFrame]:
        """Yield decoded frames asynchronously from the underlying engine."""
        async for frame in self.engine.frames_async(max_frames=max_frames):
            yield frame
