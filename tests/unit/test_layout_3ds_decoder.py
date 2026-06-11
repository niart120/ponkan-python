import json
from os import PathLike, fspath
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

import ponkan.protocol.layout_3ds as layout_3ds
from ponkan.errors import DecodeError, OptionalDependencyError
from ponkan.image.frame import CaptureFrame
from ponkan.protocol.layout_3ds import APPROVED_N3DSXL_2D_DECODER_ID, decode_rgb8_2d
from ponkan.protocol.sizes import BOTTOM_WIDTH_3DS, HEIGHT_3DS, TOP_WIDTH_3DS, video_size
from ponkan.tools.raw_to_png import main as raw_to_png_main


def _synthetic_ftd3_raw_2d() -> bytes:
    width_delta = TOP_WIDTH_3DS - BOTTOM_WIDTH_3DS
    stacked = np.zeros((TOP_WIDTH_3DS + BOTTOM_WIDTH_3DS, HEIGHT_3DS, 3), dtype=np.uint8)
    stacked[:width_delta] = [10, 11, 12]
    stacked[width_delta::2] = [4, 5, 6]
    stacked[width_delta + 1 :: 2] = [1, 2, 3]
    return stacked.tobytes()


def test_2d_synthetic_raw_decodes_to_top_bottom_shapes() -> None:
    frame = decode_rgb8_2d(_synthetic_ftd3_raw_2d())

    assert frame.top.shape == (HEIGHT_3DS, TOP_WIDTH_3DS, 3)
    assert frame.bottom.shape == (HEIGHT_3DS, BOTTOM_WIDTH_3DS, 3)
    assert frame.top.dtype == np.uint8
    assert frame.bottom.dtype == np.uint8
    assert {tuple(pixel) for pixel in frame.top.reshape(-1, 3)} == {
        (1, 2, 3),
        (10, 11, 12),
    }
    assert np.all(frame.bottom == [4, 5, 6])


def test_2d_ftd3_raw_uses_cc3dsfs_deinterleaved_layout() -> None:
    frame = decode_rgb8_2d(_synthetic_ftd3_raw_2d())

    assert frame.top.shape == (HEIGHT_3DS, TOP_WIDTH_3DS, 3)
    assert frame.bottom.shape == (HEIGHT_3DS, BOTTOM_WIDTH_3DS, 3)
    assert {tuple(pixel) for pixel in frame.top.reshape(-1, 3)} == {
        (1, 2, 3),
        (10, 11, 12),
    }
    assert np.all(frame.bottom == [4, 5, 6])


def test_decode_rejects_wrong_video_size() -> None:
    with pytest.raises(DecodeError):
        decode_rgb8_2d(b"\x00" * (video_size(False) - 1))


def test_decode_does_not_accept_decoder_version_argument() -> None:
    decoder = cast("Any", decode_rgb8_2d)

    with pytest.raises(TypeError):
        decoder(_synthetic_ftd3_raw_2d(), decoder_version=4)


def test_to_ndarray_can_return_bgr_copy() -> None:
    frame = decode_rgb8_2d(_synthetic_ftd3_raw_2d())

    bgr = frame.to_ndarray(screen="top", colorspace="BGR")

    assert bgr[0, 0].tolist() == frame.top[0, 0][::-1].tolist()
    assert not np.shares_memory(bgr, frame.top)


def test_to_mosaic_centers_bottom_screen() -> None:
    frame = decode_rgb8_2d(_synthetic_ftd3_raw_2d())

    mosaic = frame.to_mosaic(gap=2)

    assert mosaic.shape == (HEIGHT_3DS * 2 + 2, TOP_WIDTH_3DS, 3)
    assert mosaic[HEIGHT_3DS + 2, 40].tolist() == [4, 5, 6]


def test_production_layout_module_exposes_no_probe_candidate_api() -> None:
    assert not hasattr(layout_3ds, "DecoderVersion")
    assert not hasattr(layout_3ds, "iter_decoder_candidates")
    assert "decoder_version" not in layout_3ds.decode_rgb8_2d.__annotations__


def test_production_source_has_no_legacy_candidate_branch() -> None:
    source_paths = [
        Path(layout_3ds.__file__),
        Path("src/ponkan/streaming/engine.py"),
    ]

    for source_path in source_paths:
        source = source_path.read_text(encoding="utf-8")
        assert "DecoderVersion" not in source
        assert "iter_decoder_candidates" not in source
        assert "decoder_version" not in source


def test_to_pillow_is_lazy_optional_dependency() -> None:
    frame = decode_rgb8_2d(_synthetic_ftd3_raw_2d())

    try:
        image = frame.to_pillow(screen="top")
    except OptionalDependencyError:
        return
    else:
        assert image.size == (TOP_WIDTH_3DS, HEIGHT_3DS)


class _FakeImage:
    size = (1, 1)

    def save(self, fp: object) -> object:
        if not isinstance(fp, str | PathLike):
            raise TypeError
        path_value = fspath(fp)
        if isinstance(path_value, bytes):
            raise TypeError
        Path(path_value).write_bytes(b"png")
        return None


def _fake_to_pillow(self: CaptureFrame, screen: str = "top") -> _FakeImage:
    _ = self, screen
    return _FakeImage()


def test_raw_to_png_cli_writes_approved_decoder_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_path = tmp_path / "raw_2d_001.bin"
    metadata_path = tmp_path / "raw_2d_001.json"
    out_dir = tmp_path / "png"
    manifest_path = out_dir / "manual_visual_manifest.json"
    raw_path.write_bytes(_synthetic_ftd3_raw_2d() + b"transfer suffix")
    metadata_path.write_text(
        json.dumps({"video_size": video_size(False)}),
        encoding="utf-8",
    )

    monkeypatch.setattr(CaptureFrame, "to_pillow", _fake_to_pillow)

    assert (
        raw_to_png_main(
            [
                str(raw_path),
                "--metadata",
                str(metadata_path),
                "--out",
                str(out_dir),
                "--manifest",
                str(manifest_path),
            ]
        )
        == 0
    )
    assert (out_dir / "top.png").read_bytes() == b"png"
    assert (out_dir / "bottom.png").read_bytes() == b"png"
    assert not any(out_dir.glob("probe_*.png"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["metadata_path"] == str(metadata_path)
    assert manifest["manual_visual_status"] == "pending"
    assert manifest["decoder_id"] == APPROVED_N3DSXL_2D_DECODER_ID
    assert "selected_decoder_version" not in manifest
    assert len(manifest["outputs"]) == 2


def test_raw_to_png_cli_records_approved_decoder_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_path = tmp_path / "raw_2d_001.bin"
    metadata_path = tmp_path / "raw_2d_001.json"
    out_dir = tmp_path / "png"
    manifest_path = out_dir / "manual_visual_manifest.json"
    evidence_path = out_dir / "top.png"
    raw_path.write_bytes(_synthetic_ftd3_raw_2d())
    metadata_path.write_text(
        json.dumps({"video_size": video_size(False)}),
        encoding="utf-8",
    )

    monkeypatch.setattr(CaptureFrame, "to_pillow", _fake_to_pillow)

    assert (
        raw_to_png_main(
            [
                str(raw_path),
                "--metadata",
                str(metadata_path),
                "--out",
                str(out_dir),
                "--manifest",
                str(manifest_path),
                "--manual-visual-status",
                "approved",
                "--approval-evidence",
                str(evidence_path),
            ]
        )
        == 0
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["manual_visual_status"] == "approved"
    assert manifest["decoder_id"] == APPROVED_N3DSXL_2D_DECODER_ID
    assert "selected_decoder_version" not in manifest
    assert manifest["approval_evidence"] == str(evidence_path)


def test_raw_to_png_cli_rejects_removed_decoder_version_option(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw_2d_001.bin"
    out_dir = tmp_path / "png"
    raw_path.write_bytes(_synthetic_ftd3_raw_2d())

    with pytest.raises(SystemExit):
        raw_to_png_main(
            [
                str(raw_path),
                "--out",
                str(out_dir),
                "--selected-decoder-version",
                "4",
            ]
        )


def test_raw_to_png_cli_probe_candidates_are_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_path = tmp_path / "raw_2d_001.bin"
    metadata_path = tmp_path / "raw_2d_001.json"
    out_dir = tmp_path / "png"
    manifest_path = out_dir / "manual_visual_manifest.json"
    raw_path.write_bytes(_synthetic_ftd3_raw_2d())
    metadata_path.write_text(
        json.dumps({"video_size": video_size(False)}),
        encoding="utf-8",
    )

    monkeypatch.setattr(CaptureFrame, "to_pillow", _fake_to_pillow)

    assert (
        raw_to_png_main(
            [
                str(raw_path),
                "--metadata",
                str(metadata_path),
                "--out",
                str(out_dir),
                "--manifest",
                str(manifest_path),
                "--probe-candidates",
            ]
        )
        == 0
    )

    assert (out_dir / "probe_legacy_top_first_transpose_top.png").read_bytes() == b"png"
    assert (out_dir / "probe_ftd3_cc3dsfs_2d_bottom.png").read_bytes() == b"png"
    assert not (out_dir / "top.png").exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["probe_mode"] is True
    assert {probe["candidate_id"] for probe in manifest["probes"]} == {
        "legacy_top_first_transpose",
        "legacy_top_first_rotate_cw",
        "legacy_top_first_rotate_cw_flip_x",
        "ftd3_cc3dsfs_2d",
    }
    assert "selected_decoder_version" not in manifest
