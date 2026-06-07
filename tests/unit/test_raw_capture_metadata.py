import json
from pathlib import Path

import pytest

from py3dscapture.capture import RawCapture, save_raw_capture
from py3dscapture.errors import DecodeError, TransferOverflow
from py3dscapture.protocol.sizes import capture_size, video_size


def _raw_capture(
    *,
    transferred: int | None = None,
    payload_suffix: bytes = b"suffix",
) -> RawCapture:
    video = video_size(False)
    capture = capture_size(False)
    actual_transferred = transferred or capture
    payload = (b"\x11" * video) + payload_suffix + (b"\x00" * (capture - video))
    return RawCapture(
        model="new_3ds_xl",
        mode_3d=False,
        payload=payload,
        transferred=actual_transferred,
        video_size=video,
        capture_size=capture,
        timestamp_ns=123,
        sequence=7,
        metadata={"product_string": "N3DSXL", "vid": "0x0403", "pid": "0x601f"},
    )


def test_raw_capture_metadata_contains_required_keys() -> None:
    metadata = _raw_capture().to_metadata()

    assert metadata["model"] == "new_3ds_xl"
    assert metadata["product_string"] == "N3DSXL"
    assert metadata["vid"] == "0x0403"
    assert metadata["pid"] == "0x601f"
    assert metadata["mode_3d"] is False
    assert metadata["decoder_version"] is None
    assert metadata["manual_visual_status"] == "pending"
    json.dumps(metadata)


def test_transferred_shorter_than_video_size_is_rejected() -> None:
    with pytest.raises(DecodeError):
        _raw_capture(transferred=video_size(False) - 1)


def test_transferred_larger_than_capture_size_is_rejected() -> None:
    with pytest.raises(TransferOverflow):
        _raw_capture(transferred=capture_size(False) + 1)


def test_video_region_returns_only_video_prefix() -> None:
    capture = _raw_capture(payload_suffix=b"\x22" * 32)

    assert capture.video_region() == b"\x11" * video_size(False)


def test_save_raw_capture_writes_bin_and_metadata(tmp_path: Path) -> None:
    capture = _raw_capture()

    bin_path, metadata_path = save_raw_capture(capture, tmp_path / "raw_2d_001.bin")

    assert bin_path.read_bytes() == capture.payload[: capture.transferred]
    assert json.loads(metadata_path.read_text(encoding="utf-8"))["sequence"] == 7
    with pytest.raises(FileExistsError):
        save_raw_capture(capture, bin_path)
