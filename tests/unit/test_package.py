import tomllib
from pathlib import Path

import py3dscapture

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_package_imports() -> None:
    assert py3dscapture.N3DSXL_VENDOR_ID == 0x0403
    assert "capture_sizes" in py3dscapture.__all__
    assert "open_capture" in py3dscapture.__all__
    assert py3dscapture.CaptureOutput.BOTH_VERTICAL == "both_vertical"


def test_pyproject_declares_publish_metadata() -> None:
    pyproject = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["name"] == "ponkan-python"
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE", "NOTICE.md"]
    for path in project["license-files"]:
        assert (_PROJECT_ROOT / path).is_file()

    urls = project["urls"]
    assert urls["Documentation"].endswith("/docs/api.md")
    assert urls["Repository"] == "https://github.com/niart120/ponkan-python.git"

    scripts = project["scripts"]
    assert scripts == {
        "py3dscapture-capture-raw": "py3dscapture.tools.capture_raw:main",
        "py3dscapture-list-devices": "py3dscapture.tools.list_devices:main",
        "py3dscapture-raw-to-png": "py3dscapture.tools.raw_to_png:main",
        "py3dscapture-stream-n3dsxl": "py3dscapture.tools.stream_n3dsxl:main",
    }
