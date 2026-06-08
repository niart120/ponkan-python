import json
import os
from pathlib import Path

import pytest

from py3dscapture.errors import OptionalDependencyError
from py3dscapture.protocol.layout_3ds import APPROVED_N3DSXL_2D_DECODER_ID
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

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["manual_visual_status"] == "pending"
    assert manifest["decoder_id"] == APPROVED_N3DSXL_2D_DECODER_ID
    assert "selected_decoder_version" not in manifest
    assert (out_dir / "top.png").is_file()
    assert (out_dir / "bottom.png").is_file()
    assert len(manifest["outputs"]) == 2

    probe_out_dir = out_dir / "probe"
    probe_manifest_path = probe_out_dir / "manual_visual_probe_manifest.json"
    probe_argv = [
        str(raw_path),
        "--out",
        str(probe_out_dir),
        "--manifest",
        str(probe_manifest_path),
        "--force",
        "--probe-candidates",
    ]
    if metadata_path is not None:
        probe_argv.extend(["--metadata", str(metadata_path)])

    assert raw_to_png_main(probe_argv) == 0

    assert (probe_out_dir / "probe_legacy_top_first_transpose_top.png").is_file()
    assert (probe_out_dir / "probe_ftd3_cc3dsfs_2d_bottom.png").is_file()
    probe_manifest = json.loads(probe_manifest_path.read_text(encoding="utf-8"))
    assert probe_manifest["probe_mode"] is True
    assert "selected_decoder_version" not in probe_manifest


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
