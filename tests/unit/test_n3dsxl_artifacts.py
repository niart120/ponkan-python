import json
from pathlib import Path

import pytest

from ponkan.artifacts import n3dsxl_artifact_dir, write_json_artifact


def test_n3dsxl_artifact_dir_stays_under_artifact_root(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"

    assert n3dsxl_artifact_dir("20260607T120000", root=root) == (
        root / "n3dsxl" / "20260607T120000"
    )


def test_n3dsxl_artifact_dir_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid artifact run_id"):
        n3dsxl_artifact_dir("../outside", root=tmp_path / "artifacts")


def test_write_json_artifact_refuses_overwrite_without_force(tmp_path: Path) -> None:
    path = tmp_path / "artifacts" / "n3dsxl" / "run" / "stream_stats.json"

    write_json_artifact(path, {"submitted": 1})

    with pytest.raises(FileExistsError):
        write_json_artifact(path, {"submitted": 2})

    write_json_artifact(path, {"submitted": 3}, force=True)

    assert json.loads(path.read_text(encoding="utf-8")) == {"submitted": 3}
