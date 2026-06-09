import py3dscapture


def test_package_imports() -> None:
    assert py3dscapture.N3DSXL_VENDOR_ID == 0x0403
    assert "capture_sizes" in py3dscapture.__all__
    assert "open_capture" in py3dscapture.__all__
    assert py3dscapture.CaptureOutput.BOTH_VERTICAL == "both_vertical"
