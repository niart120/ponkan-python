from py3dscapture.protocol.sizes import (
    ACCEPTED_N3DSXL_PRODUCT_IDS,
    ACCEPTED_N3DSXL_PRODUCT_STRINGS,
    N3DSXL_BULK_IN_ENDPOINT,
    N3DSXL_BULK_INTERFACE,
    N3DSXL_BULK_OUT_ENDPOINT,
    N3DSXL_COMMAND_INTERFACE,
    N3DSXL_DEFAULT_CONFIGURATION,
    N3DSXL_FTD3_COMMAND_PIPE_ID,
    N3DSXL_VENDOR_ID,
    capture_sizes,
)


def test_n3dsxl_usb_identity_constants_match_spec() -> None:
    assert N3DSXL_VENDOR_ID == 0x0403
    assert frozenset({0x601E, 0x601F, 0x602A, 0x602B, 0x602C, 0x602D, 0x602F}) == (
        ACCEPTED_N3DSXL_PRODUCT_IDS
    )
    assert frozenset({"N3DSXL", "N3DSXL.2"}) == ACCEPTED_N3DSXL_PRODUCT_STRINGS


def test_n3dsxl_usb_interface_constants_match_spec() -> None:
    assert N3DSXL_COMMAND_INTERFACE == 0
    assert N3DSXL_BULK_INTERFACE == 1
    assert N3DSXL_BULK_OUT_ENDPOINT == 0x02
    assert N3DSXL_BULK_IN_ENDPOINT == 0x82
    assert N3DSXL_FTD3_COMMAND_PIPE_ID == 0x01
    assert N3DSXL_DEFAULT_CONFIGURATION == 1


def test_n3dsxl_2d_capture_sizes_match_spec() -> None:
    sizes = capture_sizes(mode_3d=False)

    assert sizes.video_size == 518400
    assert sizes.audio_size == 35072
    assert sizes.struct_total_before_1024_floor == 555520
    assert sizes.capture_size == 555008
    assert sizes.max_non_error_transferred == 553984


def test_n3dsxl_3d_capture_sizes_match_spec() -> None:
    sizes = capture_sizes(mode_3d=True)

    assert sizes.video_size == 806400
    assert sizes.audio_size == 35072
    assert sizes.struct_total_before_1024_floor == 843520
    assert sizes.capture_size == 842752
    assert sizes.max_non_error_transferred == 841728
