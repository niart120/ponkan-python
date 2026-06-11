"""Artifact helpers for hardware-gated capture evidence."""

import json
from collections.abc import Mapping
from pathlib import Path


class ArtifactPathError(ValueError):
    """Raised when an artifact run id escapes the N3DSXL artifact root.

    This prevents absolute paths and parent-directory traversal from being used
    as hardware evidence run IDs.
    """

    def __init__(self) -> None:
        """Create an artifact path error with a stable user-facing message.

        The message is intentionally short because path details can come from
        user-controlled run IDs.
        """
        super().__init__("invalid artifact run_id")


def n3dsxl_artifact_dir(run_id: str, *, root: Path = Path("artifacts")) -> Path:
    """Return the artifact directory for one N3DSXL run.

    Args:
        run_id: Relative run identifier used below ``root / "n3dsxl"``.
        root: Artifact root directory.

    Returns:
        Path where N3DSXL evidence for the run should be written.

    Raises:
        ArtifactPathError: ``run_id`` is absolute or contains ``..``.
    """
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
    """Write a JSON artifact, refusing overwrite unless force is set.

    Args:
        path: Destination JSON artifact path.
        data: JSON-serializable mapping to write.
        force: Overwrite an existing file when true.

    Returns:
        The path written by this call.

    Raises:
        FileExistsError: The artifact already exists and ``force`` is false.
    """
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path
