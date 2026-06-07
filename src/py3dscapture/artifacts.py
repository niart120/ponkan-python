"""Artifact helpers for hardware-gated capture evidence."""

import json
from collections.abc import Mapping
from pathlib import Path


class ArtifactPathError(ValueError):
    """Raised when an artifact run id escapes the N3DSXL artifact root."""

    def __init__(self) -> None:
        """Create an artifact path error."""
        super().__init__("invalid artifact run_id")


def n3dsxl_artifact_dir(run_id: str, *, root: Path = Path("artifacts")) -> Path:
    """Return the artifact directory for one N3DSXL run."""
    run_path = Path(run_id)
    if run_path.is_absolute() or ".." in run_path.parts:
        raise ArtifactPathError
    return root / "n3dsxl" / run_path


def write_json_artifact(
    path: Path,
    data: Mapping[str, object],
    *,
    force: bool = False,
) -> Path:
    """Write a JSON artifact, refusing overwrite unless force is set."""
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path
