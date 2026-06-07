"""Convert raw N3DSXL fixtures to candidate PNG images."""

import argparse
from pathlib import Path

from py3dscapture.protocol.layout_3ds import iter_decoder_candidates


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    raw_video = args.raw.read_bytes()
    args.out.mkdir(parents=True, exist_ok=True)
    for version, frame in iter_decoder_candidates(raw_video):
        for screen in ("top", "bottom"):
            out_path = args.out / f"candidate_{version}_{screen}.png"
            if out_path.exists() and not args.force:
                raise FileExistsError
            frame.to_pillow(screen=screen).save(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
