"""Convert raw N3DSXL fixtures to candidate PNG images."""

import argparse
import json
from pathlib import Path

from py3dscapture.protocol.layout_3ds import iter_decoder_candidates


class ManualVisualSelectionError(ValueError):
    """Raised when manual visual approval metadata is inconsistent."""

    def __init__(self) -> None:
        """Create an approval metadata error."""
        super().__init__("invalid manual visual approval metadata")


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
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
    parser.add_argument("--selected-decoder-version", type=int)
    parser.add_argument("--approval-evidence", type=Path)
    args = parser.parse_args(argv)

    raw_video = _read_raw_video(args.raw, args.metadata)
    args.out.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, object]] = []
    for version, frame in iter_decoder_candidates(raw_video):
        for screen in ("top", "bottom"):
            out_path = args.out / f"candidate_{version}_{screen}.png"
            if out_path.exists() and not args.force:
                raise FileExistsError
            image = frame.to_pillow(screen=screen)
            image.save(out_path)
            outputs.append(
                {
                    "decoder_version": version,
                    "screen": screen,
                    "path": str(out_path),
                    "width": image.size[0],
                    "height": image.size[1],
                }
            )
    _validate_manual_visual_selection(
        manual_visual_status=args.manual_visual_status,
        selected_decoder_version=args.selected_decoder_version,
        outputs=outputs,
    )
    if args.manifest is not None:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(
                {
                    "raw_path": str(args.raw),
                    "metadata_path": str(args.metadata) if args.metadata is not None else None,
                    "out_dir": str(args.out),
                    "manual_visual_status": args.manual_visual_status,
                    "selected_decoder_version": args.selected_decoder_version,
                    "approval_evidence": (
                        str(args.approval_evidence) if args.approval_evidence is not None else None
                    ),
                    "outputs": outputs,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    return 0


def _validate_manual_visual_selection(
    *,
    manual_visual_status: str,
    selected_decoder_version: int | None,
    outputs: list[dict[str, object]],
) -> None:
    if selected_decoder_version is not None and manual_visual_status != "approved":
        raise ManualVisualSelectionError
    if manual_visual_status == "approved" and selected_decoder_version is None:
        raise ManualVisualSelectionError
    output_versions = {
        output["decoder_version"]
        for output in outputs
        if isinstance(output.get("decoder_version"), int)
    }
    if selected_decoder_version is not None and selected_decoder_version not in output_versions:
        raise ManualVisualSelectionError


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
