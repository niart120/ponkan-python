import json
import os
from pathlib import Path

import pytest

from py3dscapture.errors import OptionalDependencyError
from py3dscapture.tools.raw_to_png import main as raw_to_png_main

pytestmark = pytest.mark.manual_visual


def test_n3dsxl_raw_fixture_manual_visual_artifacts() -> None:
    raw_path = _required_file_env("PONKAN_MANUAL_VISUAL_RAW")
    out_dir = _required_dir_env("PONKAN_MANUAL_VISUAL_OUT")
    metadata_path = _metadata_path(raw_path)
    manifest_path = out_dir / "manual_visual_manifest.json"

    argv = [
        str(raw_path),
        "--out",
        str(out_dir),
        "--manifest",
        str(manifest_path),
        "--force",
    ]
    if metadata_path is not None:
        argv.extend(["--metadata", str(metadata_path)])

    try:
        assert raw_to_png_main(argv) == 0
    except OptionalDependencyError as exc:
        pytest.skip(str(exc))

    for decoder_version in range(4):
        assert (out_dir / f"candidate_{decoder_version}_top.png").is_file()
        assert (out_dir / f"candidate_{decoder_version}_bottom.png").is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["manual_visual_status"] == "pending"
    assert manifest["selected_decoder_version"] is None
    assert len(manifest["outputs"]) == 8


def _required_file_env(name: str) -> Path:
    value = os.environ.get(name)
    if value is None:
        pytest.skip(f"set {name} to a raw N3DSXL .bin fixture")
    path = Path(value)
    assert path.is_file(), f"{name} does not point to a file: {path}"
    return path


def _required_dir_env(name: str) -> Path:
    value = os.environ.get(name)
    if value is None:
        pytest.skip(f"set {name} to the manual visual artifact directory")
    path = Path(value)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _metadata_path(raw_path: Path) -> Path | None:
    value = os.environ.get("PONKAN_MANUAL_VISUAL_METADATA")
    if value is not None:
        path = Path(value)
        assert path.is_file(), f"PONKAN_MANUAL_VISUAL_METADATA does not point to a file: {path}"
        return path
    candidate = raw_path.with_suffix(".json")
    if candidate.is_file():
        return candidate
    return None
