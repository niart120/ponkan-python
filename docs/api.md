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

The package root exports the high-level reader, profile/layout/discovery
metadata, and size helpers:

```python
from ponkan import (
    ACCEPTED_N3DSXL_PRODUCT_IDS,
    ACCEPTED_N3DSXL_PRODUCT_STRINGS,
    N3DSXL_VENDOR_ID,
    CaptureConfig,
    CaptureDeviceDiscovery,
    CaptureDeviceInfo,
    CaptureLayout,
    CaptureOutput,
    CaptureProfile,
    CaptureReader,
    CaptureSizes,
    CompositeOutputInfo,
    ScreenInfo,
    UnknownCaptureLayout,
    UnknownCaptureProfile,
    capture_sizes,
    get_capture_layout,
    get_capture_profile,
    list_capture_devices,
    list_capture_layouts,
    list_capture_profiles,
    open_capture,
)
```

`__version__` is read from installed package metadata. In an editable source
tree without installed metadata it falls back to `"0.0.0"`.

## Capture Profiles

The profile registry describes implemented capture targets without enumerating,
opening, or sending commands to USB devices.

```python
from ponkan import get_capture_profile, list_capture_profiles

profiles = list_capture_profiles()
n3dsxl = get_capture_profile("n3dsxl")
same_profile = get_capture_profile("new_3ds_xl")
```

`list_capture_profiles()` returns an immutable tuple of `CaptureProfile`
metadata. The initial runtime registry contains only `n3dsxl`; future devices
such as old 3DS, classic DS, Optimize, Nisetro, and IS-family devices are not
returned before their source audit and implementation gates are complete.

`CaptureProfile` fields are stable metadata for UI and adapter selection:

| Field | N3DSXL value | Notes |
| --- | --- | --- |
| `id` | `"n3dsxl"` | Stable profile id for settings. |
| `display_name` | `"new 3DS XL"` | Human-readable label for UI. |
| `model` | `"new_3ds_xl"` | Model string accepted by `CaptureConfig`. |
| `aliases` | `("new_3ds_xl",)` | Compatibility with the existing model name. |
| `family` | `"3ds"` | Device family grouping. |
| `provider` | `"ponkan-python"` | Implementation provider for the profile. |
| `support_status` | `"stable"` | Runtime profiles are `"stable"` or `"experimental"`. |
| `default_output` | `"both_vertical"` | Matches `CaptureConfig.output`. |
| `default_colorspace` | `"RGB"` | Package default channel order. |
| `supported_colorspaces` | `("RGB", "BGR")` | Use `"BGR"` explicitly for OpenCV consumers. |
| `native_fps` | `59.8` | Initial observed N3DSXL streaming rate. |
| `screen_layout` | `"3ds_dual_screen"` | Layout metadata id for later lookup. |
| `supported_outputs` | `("top", "bottom", "both_vertical")` | Matches current `CaptureOutput` values. |
| `supports_3d` | `False` | 3D capture is outside the current MVP. |
| `supports_audio` | `False` | Audio playback/capture is outside the current MVP. |
| `supports_recording` | `False` | Recording is outside the current MVP. |

`get_capture_profile()` accepts the stable id or alias and raises
`UnknownCaptureProfile`, a `CaptureError` subclass, for unknown profile ids.

## Future Profile Roadmap

The runtime profile registry intentionally returns only implemented profiles.
The default list is `("n3dsxl",)`; future or unsupported device families are
not exposed to normal UI selection before their source audit and implementation
gates are complete.

| target / family | roadmap state | runtime registry |
| --- | --- | --- |
| `n3dsxl` / `new_3ds_xl` | implemented | Returned by `list_capture_profiles()`. |
| `old3ds` / `o3ds` | audit required | Not returned before source audit, spec, tests, and hardware gate planning. |
| `classic_ds` | audit required | Not returned before protocol, identity, command, and layout audit. |
| `optimize` | out of scope | Not returned. |
| `nisetro` | out of scope | Not returned. |
| `is_nitro` / `is_twl` / `partner_ctr` | out of scope | Not returned. |

Source audit for a future runtime profile must record VID/PID, product string
policy, command request values, endpoints/interfaces, raw capture structure,
screen layout, safe listing behavior, and the first hardware gate plan. The
audit record belongs in a dedicated source-audit Work Unit before runtime code
or public profile metadata is added.

runtime profile promotion:

```text
audit required -> audited:
  identity / command / layout facts are recorded from cc3dsfs sources.

audited -> experimental:
  implementation exists and unit / characterization tests pass.

experimental -> stable:
  hardware E2E, performance / shutdown gates, docs, and public API tests pass.
```

## Layout Metadata

Layout metadata describes the screens and output shapes exposed by profile APIs.
It does not allocate image buffers, open devices, or decode frames.

```python
from ponkan import get_capture_layout, get_capture_profile

profile = get_capture_profile("n3dsxl")
layout = get_capture_layout(profile.screen_layout)
both_vertical = next(output for output in layout.outputs if output.id == "both_vertical")
preview_shape = both_vertical.ndarray_shape
```

`list_capture_layouts()` returns the implemented runtime layouts. The initial
registry contains only `3ds_dual_screen`:

| Field | N3DSXL value | Notes |
| --- | --- | --- |
| `id` | `"3ds_dual_screen"` | Stable layout id referenced by `CaptureProfile.screen_layout`. |
| `screens` | `top`, `bottom` | `top_right` is not exposed while 3D capture is unsupported. |
| `outputs` | `top`, `bottom`, `both_vertical` | Matches current `CaptureOutput` values. |
| `aspect_hints["bottom_horizontal_offset"]` | `40` | Bottom screen is centered under the top screen. |

`ScreenInfo.ndarray_shape` and `CompositeOutputInfo.ndarray_shape` expose the
public `numpy.ndarray` shape as `(height, width, channels)`.

`ScreenInfo` fields are `id`, `display_name`, `width`, `height`, `channels`,
`colorspace`, `coordinate_space`, and `role`. `CompositeOutputInfo` fields are
`id`, `display_name`, `width`, `height`, `channels`, `screens`, `placement`,
and `default`. `CaptureLayout.aspect_hints` is a read-only mapping for
display/preview hints such as bottom-screen centering.

| Output | Shape | Placement |
| --- | --- | --- |
| `top` | `(240, 400, 3)` | Single top screen. |
| `bottom` | `(240, 320, 3)` | Single bottom screen. |
| `both_vertical` | `(480, 400, 3)` | Top screen above centered bottom screen. |

`get_capture_layout()` raises `UnknownCaptureLayout`, a `CaptureError`
subclass with `code="unsupported_layout"`, for unknown layout ids.

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
| `backend` | one of `auto`, `libusb`, `d3xx`, `d3xx-native` | `None` | Backend preference. On Windows, `auto` resolves to `d3xx-native`. |
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
| `backend` | `"auto"` | On Windows this resolves to `"d3xx-native"`. PyD3XX is a normal Windows platform dependency, not an optional extra. |
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

Backend selection note: starting with the current unreleased changes,
`backend="auto"` shares the discovery resolver and uses `"d3xx-native"` on
Windows. The sequential D3XX path remains available only through
`backend="d3xx"`. The `"libusb"` literal is accepted as a config value for
discovery parity, but the high-level opener currently rejects it with
`UnsupportedOperation`.

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
from ponkan import list_capture_devices

discovery = list_capture_devices(profile="n3dsxl", backend="auto")
```

The discovery layer does not send N3DSXL commands. It only classifies
descriptors and reports backend availability:

| Field | Meaning |
| --- | --- |
| `profile_id` | Resolved profile id such as `"n3dsxl"`. |
| `backend_preference` | Caller preference such as `"auto"` or `"libusb"`. |
| `resolved_backend` | Concrete backend used for enumeration. Windows `"auto"` resolves to `"d3xx-native"`. |
| `backend_status` | `"available"`, `"unavailable"`, or `"unsupported"`. |
| `reason` | Shared `CaptureReason` such as `"available"`, `"device_not_found"`, or `"missing_package"`. |
| `remediation` | Optional backend-level recovery guidance. |
| `devices` | Tuple of `CaptureDeviceInfo` descriptors. |

`include_rejected=True` includes FTDI-family devices rejected by the N3DSXL
safety boundary. Rejected devices are useful for diagnostics but should not be
offered as normal capture targets.

`CaptureDeviceInfo` fields:

| Field | Meaning |
| --- | --- |
| `id` | Backend-prefixed stable-or-best-effort identifier. |
| `display_name` | Product string or fallback human-readable label. |
| `profile_id` | Profile this descriptor was classified for. |
| `model` | Resolved capture model, or `"unknown"` for rejected devices. |
| `backend` | Concrete backend that enumerated the descriptor. |
| `backend_preference` | Original caller preference. |
| `vendor_id` / `product_id` | USB identity fields when visible. |
| `serial_number` | Serial number when visible. |
| `product_string` | Product string when readable. |
| `product_string_status` | `"accepted"`, `"unreadable"`, `"rejected"`, or `"unknown"`. |
| `connection_status` | `"available"`, `"rejected"`, `"unsupported"`, or `"unknown"`. |
| `id_stability` | `"stable"` for serial ids, `"session"` for bus/address ids, or `"unknown"`. |
| `reason` | Device-level `CaptureReason`. |
| `remediation` | Optional diagnostic detail such as a rejected product-string reason. |

Dependency absence, such as missing PyD3XX, is returned as
`backend_status="unavailable"`. Native backend API failures while enumerating
descriptors may still propagate as `CaptureError` subclasses such as
`D3xxBackendError`; those failures expose backend-specific `function`,
`status`, and `field_name` attributes.

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
| `ponkan-list-devices` | Print accepted and rejected FTDI-family devices through the libusb descriptor path without sending N3DSXL commands. |
| `ponkan-capture-raw --out <path>` | Capture one raw frame and metadata sidecar. |
| `ponkan-raw-to-png <raw> --metadata <json> --out <dir>` | Decode raw video to top and bottom PNG files. |
| `ponkan-stream-n3dsxl --duration 10 --stats` | Run a bounded streaming smoke loop and print counters. |

Hardware commands should only be run after confirming the device identity and
the project hardware safety policy.

## Error Types

All package-level failures inherit from `CaptureError`.

Every `CaptureError` exposes common structured fields while preserving the
existing exception class hierarchy and `str(error)` message:

| Field | Meaning |
| --- | --- |
| `code` | Stable error category such as `"device_not_found"` or `"decode_failed"`. |
| `profile` | Capture profile context when known, such as `"n3dsxl"`. |
| `backend` | Backend context when known, such as `"d3xx"` or `"d3xx-native"`. |
| `reason` | Shared discovery/error reason such as `"missing_package"` or `"open_failed"`. |
| `recoverable` | Whether reconnect, install, driver, or settings changes may recover. |
| `remediation` | Short user-facing recovery guidance when available. |

```python
from ponkan.errors import CaptureError
from ponkan.transport.d3xx_backend import D3xxBackendError

try:
    ...
except CaptureError as exc:
    technical_log = exc.to_dict()
    status_code = exc.code
```

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
| `UnknownCaptureProfile` | A profile id or alias is not in the runtime profile registry. |
| `UnknownCaptureLayout` | A layout id is not in the runtime layout registry. |
| `D3xxBackendError` | Native D3XX binding call or descriptor parsing failed. |

`D3xxBackendError` is transport-specific and is imported from
`ponkan.transport.d3xx_backend`, not from the package root. It preserves the
existing message format and exposes common structured fields:
`code="d3xx_backend_failed"`, `backend="d3xx"`, `recoverable=True`, and
`reason="open_failed"` for native API/open-path failures. Descriptor parsing
failures such as missing or invalid detail fields use `reason="read_failed"`.

For technical logs, `D3xxBackendError` also carries backend-specific context
through `function`, `status`, and `field_name`.
