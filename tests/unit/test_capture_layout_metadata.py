import numpy as np
import pytest

from ponkan import CaptureOutput, get_capture_profile
from ponkan.image.frame import CaptureFrame
from ponkan.layouts import UnknownCaptureLayout, get_capture_layout


def test_n3dsxl_layout_exposes_top_and_bottom_screen_metadata() -> None:
    layout = get_capture_layout("3ds_dual_screen")

    assert layout.id == "3ds_dual_screen"
    assert tuple(screen.id for screen in layout.screens) == ("top", "bottom")
    assert "top_right" not in tuple(screen.id for screen in layout.screens)

    top, bottom = layout.screens
    assert top.display_name == "Top Screen"
    assert top.width == 400
    assert top.height == 240
    assert top.channels == 3
    assert top.ndarray_shape == (240, 400, 3)
    assert top.coordinate_space == "top_pixels"
    assert top.role == "primary"

    assert bottom.display_name == "Bottom Screen"
    assert bottom.width == 320
    assert bottom.height == 240
    assert bottom.ndarray_shape == (240, 320, 3)
    assert bottom.coordinate_space == "bottom_pixels"
    assert bottom.role == "touch"


def test_both_vertical_composite_matches_existing_mosaic_shape() -> None:
    layout = get_capture_layout("3ds_dual_screen")
    output = next(item for item in layout.outputs if item.id == "both_vertical")

    assert output.width == 400
    assert output.height == 480
    assert output.channels == 3
    assert output.ndarray_shape == (480, 400, 3)
    assert output.screens == ("top", "bottom")
    assert output.placement == "top_above_bottom_centered"
    assert output.default


def test_capture_output_values_match_layout_supported_outputs() -> None:
    layout = get_capture_layout("3ds_dual_screen")

    assert tuple(item.value for item in CaptureOutput) == tuple(
        output.id for output in layout.outputs
    )


def test_profile_screen_layout_resolves_to_supported_layout() -> None:
    profile = get_capture_profile("n3dsxl")
    layout = get_capture_layout(profile.screen_layout)

    assert layout.id == "3ds_dual_screen"
    assert profile.default_output == "both_vertical"
    assert profile.default_colorspace == "RGB"
    assert profile.supported_colorspaces == ("RGB", "BGR")
    assert profile.supported_outputs == tuple(output.id for output in layout.outputs)


def test_layout_metadata_matches_capture_frame_shapes() -> None:
    layout = get_capture_layout("3ds_dual_screen")
    top = np.zeros(layout.screens[0].ndarray_shape, dtype=np.uint8)
    bottom = np.zeros(layout.screens[1].ndarray_shape, dtype=np.uint8)
    frame = CaptureFrame(
        top=top,
        bottom=bottom,
        top_right=None,
        timestamp_ns=None,
        source_model="new_3ds_xl",
        mode_3d=False,
    )

    assert frame.to_ndarray("top").shape == layout.screens[0].ndarray_shape
    assert frame.to_ndarray("bottom").shape == layout.screens[1].ndarray_shape
    assert frame.to_mosaic(gap=0).shape == layout.outputs[2].ndarray_shape


def test_unknown_layout_raises_explicit_error() -> None:
    with pytest.raises(UnknownCaptureLayout) as exc_info:
        get_capture_layout("bogus")

    assert exc_info.value.code == "unsupported_layout"
