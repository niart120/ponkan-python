import json
from os import PathLike, fspath
from pathlib import Path

import numpy as np
import pytest

from py3dscapture.errors import DecodeError, OptionalDependencyError
from py3dscapture.image.frame import CaptureFrame
from py3dscapture.protocol.layout_3ds import decode_rgb8_2d, iter_decoder_candidates
from py3dscapture.protocol.sizes import BOTTOM_WIDTH_3DS, HEIGHT_3DS, TOP_WIDTH_3DS, video_size
from py3dscapture.tools.raw_to_png import main as raw_to_png_main


def _synthetic_raw_2d() -> bytes:
    stacked = np.zeros((TOP_WIDTH_3DS + BOTTOM_WIDTH_3DS, HEIGHT_3DS, 3), dtype=np.uint8)
    stacked[:TOP_WIDTH_3DS] = [1, 2, 3]
    stacked[TOP_WIDTH_3DS:] = [4, 5, 6]
    return stacked.tobytes()


def test_2d_synthetic_raw_decodes_to_top_bottom_shapes() -> None:
    frame = decode_rgb8_2d(_synthetic_raw_2d(), decoder_version=1)

    assert frame.top.shape == (HEIGHT_3DS, TOP_WIDTH_3DS, 3)
    assert frame.bottom.shape == (HEIGHT_3DS, BOTTOM_WIDTH_3DS, 3)
    assert frame.top.dtype == np.uint8
    assert frame.bottom.dtype == np.uint8
    assert frame.top[0, 0].tolist() == [1, 2, 3]
    assert frame.bottom[0, 0].tolist() == [4, 5, 6]


def test_decode_rejects_wrong_video_size() -> None:
    with pytest.raises(DecodeError):
        decode_rgb8_2d(b"\x00" * (video_size(False) - 1), decoder_version=1)


def test_to_ndarray_can_return_bgr_copy() -> None:
    frame = decode_rgb8_2d(_synthetic_raw_2d(), decoder_version=1)

    bgr = frame.to_ndarray(screen="top", colorspace="BGR")

    assert bgr[0, 0].tolist() == [3, 2, 1]
    assert not np.shares_memory(bgr, frame.top)


def test_to_mosaic_centers_bottom_screen() -> None:
    frame = decode_rgb8_2d(_synthetic_raw_2d(), decoder_version=1)

    mosaic = frame.to_mosaic(gap=2)

    assert mosaic.shape == (HEIGHT_3DS * 2 + 2, TOP_WIDTH_3DS, 3)
    assert mosaic[0, 0].tolist() == [1, 2, 3]
    assert mosaic[HEIGHT_3DS + 2, 40].tolist() == [4, 5, 6]


def test_decoder_candidates_return_multiple_versions() -> None:
    candidates = list(iter_decoder_candidates(_synthetic_raw_2d()))

    assert {version for version, _frame in candidates} == {0, 1, 2, 3}


def test_to_pillow_is_lazy_optional_dependency() -> None:
    frame = decode_rgb8_2d(_synthetic_raw_2d(), decoder_version=1)

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


def test_raw_to_png_cli_writes_candidate_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_path = tmp_path / "raw_2d_001.bin"
    metadata_path = tmp_path / "raw_2d_001.json"
    out_dir = tmp_path / "png"
    manifest_path = out_dir / "manual_visual_manifest.json"
    raw_path.write_bytes(_synthetic_raw_2d() + b"transfer suffix")
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
    assert (out_dir / "candidate_0_top.png").read_bytes() == b"png"
    assert (out_dir / "candidate_3_bottom.png").read_bytes() == b"png"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["metadata_path"] == str(metadata_path)
    assert manifest["manual_visual_status"] == "pending"
    assert manifest["selected_decoder_version"] is None
    assert len(manifest["outputs"]) == 8
