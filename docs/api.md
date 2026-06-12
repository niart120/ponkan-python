# API Reference

`ponkan` exposes a small public API for new 3DS XL capture board frame
acquisition. The current package is focused on 2D N3DSXL video capture and does
not provide GUI, audio playback, recording, old DS, Optimize, Nisetro, or IS
device support.

## Installation

```console
pip install ponkan-python
pip install "ponkan-python[image]"
```

Use the `image` extra when calling `CaptureFrame.to_pillow()` or the
`ponkan-raw-to-png` command. On Windows, the D3XX backend uses PyD3XX as a
normal platform-gated dependency.

## Top-Level Imports

The package root exports the high-level reader and size helpers:

```python
from ponkan import (
    ACCEPTED_N3DSXL_PRODUCT_IDS,
    ACCEPTED_N3DSXL_PRODUCT_STRINGS,
    N3DSXL_VENDOR_ID,
    CaptureConfig,
    CaptureOutput,
    CaptureReader,
    CaptureSizes,
    capture_sizes,
    open_capture,
)
```

`__version__` is read from installed package metadata. In an editable source
tree without installed metadata it falls back to `"0.0.0"`.

## High-Level Capture

### `open_capture(...) -> CaptureReader`

Open a high-level streaming reader for an accepted new 3DS XL capture board.

```python
from ponkan import CaptureOutput, open_capture

with open_capture(output=CaptureOutput.BOTH_VERTICAL) as cap:
    image = cap.read()
```

Arguments:

| Argument | Type | Default | Notes |
| --- | --- | --- | --- |
| `source` | `int` or `str` | `0` | `0` and `"new_3ds_xl"` are accepted. |
| `config` | `CaptureConfig` or `None` | `None` | Base configuration. Explicit keyword overrides win. |
| `backend` | one of `auto`, `libusb`, `d3xx`, `d3xx-native` | `None` | Backend preference. `auto` currently resolves to D3XX. |
| `output` | `CaptureOutput`, `str`, or `None` | `None` | Default layout returned by `read()`. |
| `colorspace` | `RGB`, `BGR`, or `None` | `None` | Default channel order returned by `read()`. |
| `read_timeout` | `float` or `None` | unchanged | Default timeout in seconds. |

Raises:

| Exception | Meaning |
| --- | --- |
| `DeviceNotFound` | No accepted N3DSXL device is visible to the selected backend. |
| `UnsupportedOperation` | The requested source, model, mode, or backend path is outside current scope. |
| `ValueError` | A config field such as backend, colorspace, queue size, or timeout is invalid. |
| `Ftd3CommandError` | Hardware command or bulk transfer setup failed. |

The reader owns the streaming engine and backend handle. Prefer `with
open_capture(...) as cap:` so `close()` is called even when reads fail.

### `CaptureConfig`

`CaptureConfig` groups the high-level reader settings.

| Field | Default | Notes |
| --- | --- | --- |
| `source` | `0` | Source selector. |
| `model` | `"new_3ds_xl"` | Only new 3DS XL is supported. |
| `backend` | `"auto"` | `"d3xx"` and `"d3xx-native"` require the `d3xx` extra. |
| `mode_3d` | `False` | `True` is rejected in the current MVP. |
| `output` | `CaptureOutput.BOTH_VERTICAL` | Default layout for `read()`. |
| `colorspace` | `"RGB"` | `"BGR"` is useful for OpenCV. |
| `raw_slots` | `2` | Number of backend raw read slots. |
| `output_queue_size` | `2` | Decoded frame queue capacity. |
| `drop_policy` | `"drop_oldest"` | One of `"drop_oldest"`, `"drop_newest"`, or `"block"`. |
| `poll_interval` | `0.004` | Poll sleep in seconds while waiting for frames. |
| `read_timeout` | `1.0` | `None` waits indefinitely. |
| `collect_timing` | `False` | Enables timing samples in streaming stats. |

### `CaptureReader`

`CaptureReader.read()` returns a copied `numpy.ndarray` or `None` on timeout.

```python
top_bgr = cap.read(output=CaptureOutput.TOP, colorspace="BGR")
```

`CaptureReader.read_frame()` returns a `CaptureFrame` with separate top and
bottom screens:

```python
frame = cap.read_frame(timeout=0.5)
if frame is not None:
    top = frame.top
    bottom = frame.bottom
```

`CaptureReader.stats()` returns a `StreamStats` snapshot from the underlying
streaming engine. `CaptureReader.close()` is idempotent and stops acquisition.

## Frames

### `CaptureFrame`

`CaptureFrame` stores decoded RGB8 arrays:

| Attribute | Shape | Notes |
| --- | --- | --- |
| `top` | `(240, 400, 3)` | Top screen RGB8 image. |
| `bottom` | `(240, 320, 3)` | Bottom screen RGB8 image. |
| `top_right` | `None` or `(240, 400, 3)` | Right-eye top screen for 3D captures. Currently `None` for MVP reads. |

Methods:

| Method | Purpose |
| --- | --- |
| `to_ndarray(screen="top", colorspace="RGB")` | Return a copied RGB or BGR array for one screen. |
| `to_pillow(screen="top")` | Return a Pillow RGB image. Requires `ponkan-python[image]`. |
| `to_mosaic(gap=0)` | Return top and centered bottom screens in one RGB array. |

`DecodeError` is raised for unavailable screens, invalid shapes, invalid dtypes,
or unsupported color-space conversion.

## Raw Capture Artifacts

### `RawCapture`

`RawCapture` represents one raw transfer plus metadata. The `video_region()`
method returns the leading RGB8 video bytes and excludes audio, unused, and
error-buffer regions. `to_metadata()` returns JSON-serializable sidecar data.

### `save_raw_capture(capture, out_path, force=False)`

Write a raw payload and metadata sidecar using the same stem:

```python
from pathlib import Path
from ponkan.capture import save_raw_capture

bin_path, metadata_path = save_raw_capture(capture, Path("captures/raw_2d_001.bin"))
```

The function returns `(bin_path, metadata_path)` and raises `FileExistsError`
unless `force=True` is provided.

## Device Discovery

```python
from ponkan.devices.n3dsxl_ftd3 import list_n3dsxl_devices
from ponkan.transport.libusb_backend import Usb1Backend

listing = list_n3dsxl_devices(Usb1Backend())
```

The discovery layer does not send N3DSXL commands. It only classifies USB
descriptors:

| Type | Meaning |
| --- | --- |
| `DeviceCandidate` | Accepted VID/PID and accepted or unreadable product string. |
| `RejectedDevice` | FTDI-family device rejected before commands may be sent. |
| `DeviceListing` | Tuple groups of candidates and rejected devices. |

Accepted device identity is constrained by `N3DSXL_VENDOR_ID`,
`ACCEPTED_N3DSXL_PRODUCT_IDS`, and `ACCEPTED_N3DSXL_PRODUCT_STRINGS`.

## Size Helpers

```python
from ponkan import capture_sizes

sizes = capture_sizes(mode_3d=False)
print(sizes.video_size, sizes.capture_size)
```

`CaptureSizes` exposes the video payload size, audio buffer size, pre-alignment
structure size, aligned capture size, and maximum non-error transfer length.
These helpers are the public source for raw frame size calculations.

## Streaming Stats

`StreamStats` contains mutable counters for submitted, completed, decoded,
delivered, dropped, cancelled, USB error, and decode error counts. Use
`snapshot()` before reporting shared counters, and `to_dict()` for JSON output.

`PerformanceStats.from_stream_stats(...)` builds JSON-serializable smoke-test
reports, including optional timing summaries when `collect_timing=True`.

## Command Line Tools

Installed console scripts:

| Command | Purpose |
| --- | --- |
| `ponkan-list-devices` | Print accepted and rejected FTDI-family devices without sending N3DSXL commands. |
| `ponkan-capture-raw --out <path>` | Capture one raw frame and metadata sidecar. |
| `ponkan-raw-to-png <raw> --metadata <json> --out <dir>` | Decode raw video to top and bottom PNG files. |
| `ponkan-stream-n3dsxl --duration 10 --stats` | Run a bounded streaming smoke loop and print counters. |

Hardware commands should only be run after confirming the device identity and
the project hardware safety policy.

## Error Types

All package-level failures inherit from `CaptureError`.

| Error | Typical cause |
| --- | --- |
| `UnsupportedDevice` | Device identity did not pass the N3DSXL safety boundary. |
| `DeviceNotFound` | No accepted device is visible. |
| `DeviceOpenError` | USB open, configuration, interface claim, release, or close failed. |
| `Ftd3CommandError` | Pipe command, read, or write failed. |
| `UnsupportedOperation` | Requested behavior is outside current MVP scope. |
| `TransferOverflow` | Transfer length exceeds the accepted capture size. |
| `DecodeError` | Raw bytes or decoded frame data cannot be interpreted. |
| `DependencyUnavailableError` | A runtime dependency required by the selected backend is unavailable. |
| `OptionalDependencyError` | Optional dependency such as Pillow is missing. |
