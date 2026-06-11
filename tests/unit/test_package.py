import tomllib
from pathlib import Path

import ponkan

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_package_imports() -> None:
    assert ponkan.N3DSXL_VENDOR_ID == 0x0403
    assert "capture_sizes" in ponkan.__all__
    assert "open_capture" in ponkan.__all__
    assert ponkan.CaptureOutput.BOTH_VERTICAL == "both_vertical"


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
        "ponkan-capture-raw": "ponkan.tools.capture_raw:main",
        "ponkan-list-devices": "ponkan.tools.list_devices:main",
        "ponkan-raw-to-png": "ponkan.tools.raw_to_png:main",
        "ponkan-stream-n3dsxl": "ponkan.tools.stream_n3dsxl:main",
    }
