"""Convert raw N3DSXL fixtures to PNG images."""

import argparse
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from ponkan.image.frame import CaptureFrame
from ponkan.protocol.layout_3ds import APPROVED_N3DSXL_2D_DECODER_ID, decode_rgb8_2d
from ponkan.protocol.sizes import BOTTOM_WIDTH_3DS, HEIGHT_3DS, TOP_WIDTH_3DS

ProbeCandidateId = Literal[
    "legacy_top_first_transpose",
    "legacy_top_first_rotate_cw",
    "legacy_top_first_rotate_cw_flip_x",
    "ftd3_cc3dsfs_2d",
]


@dataclass(frozen=True)
class _ProbeCandidate:
    candidate_id: ProbeCandidateId
    hypothesis: str
    frame: CaptureFrame


def main(argv: list[str] | None = None) -> int:
    """Run the raw-to-PNG conversion CLI.

    Args:
        argv: Optional command-line arguments. ``None`` uses ``sys.argv`` through
            ``argparse``.

    Returns:
        Process status code. Zero means image outputs were written.

    Raises:
        FileExistsError: An output exists and ``--force`` was not provided.
        DecodeError: The selected decoder cannot decode the raw video region.
        OptionalDependencyError: Pillow is unavailable for PNG writing.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--manual-visual-status",
        choices=("pending", "approved"),
        default="pending",
    )
    parser.add_argument("--approval-evidence", type=Path)
    parser.add_argument("--probe-candidates", action="store_true")
    args = parser.parse_args(argv)

    raw_video = _read_raw_video(args.raw, args.metadata)
    args.out.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object]
    if args.probe_candidates:
        manifest = _write_probe_outputs(
            raw_video=raw_video,
            raw_path=args.raw,
            metadata_path=args.metadata,
            out_dir=args.out,
            manifest_path=args.manifest,
            force=args.force,
        )
    else:
        manifest = _write_approved_outputs(
            raw_video=raw_video,
            raw_path=args.raw,
            metadata_path=args.metadata,
            out_dir=args.out,
            force=args.force,
            manual_visual_status=args.manual_visual_status,
            approval_evidence=args.approval_evidence,
        )
    if args.manifest is not None:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return 0


def _write_approved_outputs(
    *,
    raw_video: bytes,
    raw_path: Path,
    metadata_path: Path | None,
    out_dir: Path,
    force: bool,
    manual_visual_status: str,
    approval_evidence: Path | None,
) -> dict[str, object]:
    frame = decode_rgb8_2d(raw_video)
    outputs = _write_frame_outputs(
        frame=frame,
        out_dir=out_dir,
        filename_prefix="",
        force=force,
    )
    return {
        "raw_path": str(raw_path),
        "metadata_path": str(metadata_path) if metadata_path is not None else None,
        "out_dir": str(out_dir),
        "manual_visual_status": manual_visual_status,
        "decoder_id": APPROVED_N3DSXL_2D_DECODER_ID,
        "approval_evidence": str(approval_evidence) if approval_evidence is not None else None,
        "outputs": outputs,
    }


def _write_probe_outputs(
    *,
    raw_video: bytes,
    raw_path: Path,
    metadata_path: Path | None,
    out_dir: Path,
    manifest_path: Path | None,
    force: bool,
) -> dict[str, object]:
    probes: list[dict[str, object]] = []
    for candidate in _iter_probe_candidates(raw_video):
        outputs = _write_frame_outputs(
            frame=candidate.frame,
            out_dir=out_dir,
            filename_prefix=f"probe_{candidate.candidate_id}_",
            force=force,
        )
        probes.append(
            {
                "candidate_id": candidate.candidate_id,
                "hypothesis": candidate.hypothesis,
                "manual_visual_status": "pending",
                "outputs": outputs,
            }
        )
    return {
        "raw_path": str(raw_path),
        "metadata_path": str(metadata_path) if metadata_path is not None else None,
        "out_dir": str(out_dir),
        "manifest_path": str(manifest_path) if manifest_path is not None else None,
        "probe_mode": True,
        "probes": probes,
    }


def _write_frame_outputs(
    *,
    frame: CaptureFrame,
    out_dir: Path,
    filename_prefix: str,
    force: bool,
) -> list[dict[str, object]]:
    outputs: list[dict[str, object]] = []
    for screen in ("top", "bottom"):
        out_path = out_dir / f"{filename_prefix}{screen}.png"
        if out_path.exists() and not force:
            raise FileExistsError
        image = frame.to_pillow(screen=screen)
        image.save(out_path)
        outputs.append(
            {
                "screen": screen,
                "path": str(out_path),
                "width": image.size[0],
                "height": image.size[1],
            }
        )
    return outputs


def _iter_probe_candidates(raw_video: bytes) -> Iterator[_ProbeCandidate]:
    yield _ProbeCandidate(
        candidate_id="legacy_top_first_transpose",
        hypothesis="obsolete top-first split with transpose display transform",
        frame=_decode_legacy_top_first(raw_video, transform="transpose"),
    )
    yield _ProbeCandidate(
        candidate_id="legacy_top_first_rotate_cw",
        hypothesis="obsolete top-first split with clockwise display rotation",
        frame=_decode_legacy_top_first(raw_video, transform="rotate_cw"),
    )
    yield _ProbeCandidate(
        candidate_id="legacy_top_first_rotate_cw_flip_x",
        hypothesis="obsolete top-first split with clockwise rotation and horizontal flip",
        frame=_decode_legacy_top_first(raw_video, transform="rotate_cw_flip_x"),
    )
    yield _ProbeCandidate(
        candidate_id=APPROVED_N3DSXL_2D_DECODER_ID,
        hypothesis="approved cc3dsfs FTD3 2D deinterleave layout",
        frame=decode_rgb8_2d(raw_video),
    )


def _decode_legacy_top_first(
    raw_video: bytes,
    *,
    transform: Literal["transpose", "rotate_cw", "rotate_cw_flip_x"],
) -> CaptureFrame:
    stacked = np.frombuffer(raw_video, dtype=np.uint8).reshape(
        (TOP_WIDTH_3DS + BOTTOM_WIDTH_3DS, HEIGHT_3DS, 3)
    )
    top_source = stacked[:TOP_WIDTH_3DS]
    bottom_source = stacked[TOP_WIDTH_3DS:]
    return CaptureFrame(
        top=_transform_legacy_source(top_source, transform=transform),
        bottom=_transform_legacy_source(bottom_source, transform=transform),
        top_right=None,
        timestamp_ns=None,
        source_model="new_3ds_xl",
        mode_3d=False,
        colorspace="RGB",
    )


def _transform_legacy_source(
    source: np.ndarray,
    *,
    transform: Literal["transpose", "rotate_cw", "rotate_cw_flip_x"],
) -> np.ndarray:
    if transform == "transpose":
        return source.transpose(1, 0, 2).copy()
    if transform == "rotate_cw":
        return np.rot90(source, k=-1).copy()
    return np.flip(np.rot90(source, k=-1), axis=1).copy()


def _read_raw_video(raw_path: Path, metadata_path: Path | None) -> bytes:
    raw_payload = raw_path.read_bytes()
    if metadata_path is None:
        return raw_payload

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    video_size_value = metadata.get("video_size")
    if not isinstance(video_size_value, int):
        raise TypeError
    if len(raw_payload) < video_size_value:
        raise ValueError
    return raw_payload[:video_size_value]


if __name__ == "__main__":
    raise SystemExit(main())
