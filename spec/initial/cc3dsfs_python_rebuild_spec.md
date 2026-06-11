# cc3dsfs Python Rebuild Spec: New 3DS XL Async Streaming MVP

更新日: 2026-06-06

## 目的

`cc3dsfs` のうち、new 3DS XL capture board から USB 経由で映像フレームを取得する中核部分を Python ライブラリとして再設計・再実装する。

このプロジェクトは `cc3dsfs` 全体の移植ではない。GUI 表示アプリではなく、Python から new 3DS XL capture device を開き、上画面・下画面を `numpy.ndarray` として取得し、必要に応じて Pillow / OpenCV 互換の形式へ接続できるライブラリを作る。

MVP の完了条件には、単発の raw frame 取得だけでなく、libusb async transfer による連続 streaming を含める。

---

## 参照する実装領域

主な参照元は `cc3dsfs` の以下の領域。

```text
source/CaptureDeviceSpecific/3DSCapture_FTD3/
  3dscapture_ftd3_shared.cpp
  3dscapture_ftd3_libusb_comms.cpp
  3dscapture_ftd3_libusb_acquisition.cpp
  3dscapture_ftd3_compatibility.cpp

include/CaptureDeviceSpecific/3DSCapture_FTD3/
  3dscapture_ftd3_shared.hpp
  3dscapture_ftd3_shared_general.hpp
  3dscapture_ftd3_libusb_comms.hpp
  3dscapture_ftd3_libusb_acquisition.hpp
  3dscapture_ftd3_compatibility.hpp

include/capture_structs.hpp
include/hw_defs.hpp
```

old 3DS 向けの参照領域は次。

```text
source/CaptureDeviceSpecific/usb_ds_3ds_capture.cpp
include/CaptureDeviceSpecific/usb_ds_3ds_capture.hpp
```

old 3DS は設計枠だけ確保する。実機 E2E は new 3DS XL を対象にする。

---

# 1. Scope

## 1.1 MVP 対象

MVP では new 3DS XL capture board の libusb path を対象にする。

```text
1. new 3DS XL capture device を列挙できる
2. 対象 device を安全に open できる
3. command interface / bulk interface を claim できる
4. FTD3 command pipe を通して stream に必要な command sequence を実行できる
5. 2D mode で 1 フレーム分の raw capture を取得できる
6. raw capture を .bin + .json metadata として保存できる
7. raw video 領域を RGB8 ndarray に変換できる
8. top screen / bottom screen を ndarray として取り出せる
9. Pillow Image へ変換できる
10. PNG 出力の向き・色・画面分割を実機で確認できる
11. libusb async transfer / callback 相当の非同期 read pipeline で連続 streaming できる
12. USB acquisition、decode、consumer delivery を分離する
13. bounded queue と frame drop policy を持つ
14. streaming 中の stats を取得できる
15. shutdown 時に pending transfer cancel、interface release、handle close を完了できる
16. 実機 E2E で performance smoke test を通す
```

`single raw frame capture` は MVP の完了条件ではなく、streaming 実装の前に通す bring-up gate として扱う。MVP 完了条件は `async streaming E2E` まで。

## 1.2 後続対象

old 3DS / Loopy USB capture board は後続対象。

```text
- cc3dsfs の usb_ds_3ds_capture.cpp 相当
- VID/PID, vendor request, bulk IN read, capture start, 3D config read
- 実機がない間は静的 fixture・単体テスト・source reading に留める
```

new 3DS XL と old 3DS を早期に同一 transport へ押し込まない。共通化は data model、image adapter、RGB8 3DS layout decoder から始める。

## 1.3 非対象

MVP では以下を実装しない。

```text
- cc3dsfs GUI
- SFML rendering
- fullscreen / split window / crop / layout settings
- keyboard shortcuts
- profile management
- audio playback
- video encoding
- ffmpeg integration
- old DS
- Optimize / Nisetro / IS Nitro / IS TWL / Partner CTR
- FTD3XX / D2XX vendor driver backend
- multiprocessing / shared memory
- GPU acceleration
- streaming 中の 3D mode 切替
```

`audio_data` は new 3DS XL の raw capture struct に含まれるが、MVP では保存・解析用 metadata に留め、利用者向け API としては返さない。

---

# 2. 互換方針

このプロジェクトは `cc3dsfs` の公開 API 互換移植ではない。Python 版では新しい API を設計する。

## 2.1 保持するもの

```text
- new 3DS XL capture board の認識条件
- cc3dsfs が行っている FTD3 / libusb command sequence
- raw capture size の考え方
- RGB8 video buffer の解釈
- 画像として正しく復元するための画面分割・向き・色順
- async transfer / callback + 複数 in-flight buffer という streaming 構造
- error 発生時に pending transfer を cancel して停止する考え方
```

## 2.2 再設計するもの

```text
- C++ / SFML 表示アプリではなく Python ライブラリにする
- image layer は ndarray 中心にする
- top / bottom / top_right を明示的に扱う
- Pillow / OpenCV は adapter または互換出力に留める
- libusb backend を最初の基準にする
- streaming API は Python の iterator / async iterator として提供する
```

## 2.3 対象外にするもの

```text
- GUI 表示
- audio playback
- profile / crop / window 操作
- old DS / 非 Loopy 系 device
- FTD3XX / D2XX vendor driver backend
- synchronous-only MVP
```

---

# 3. Device Priority

## 3.1 Tier 0: new 3DS XL / N3DSXL

new 3DS XL capture device は `3DSCapture_FTD3` 系に対応する。

観測事項:

```text
Device short name: N3DSXL
Accepted product strings: N3DSXL, N3DSXL.2
FTDI VID: 0x0403
Accepted PIDs:
  0x601e, 0x601f, 0x602a, 0x602b, 0x602c, 0x602d, 0x602f
Command interface: 0
Bulk interface: 1
Bulk OUT endpoint: 0x02
Bulk IN endpoint: 0x82
FTD3 command pipe id: 0x01
Default configuration: 1
```

new 3DS XL は単純な bulk IN device として扱わない。FTD3 command wrapper を通して pipe create / abort / set stream / read-write prepare を行い、その後 bulk IN / OUT を使う。

必要な層:

```text
libusb primitive
  control_transfer_in/out
  bulk_transfer_in/out
  detach_kernel_driver
  set_configuration
  claim_interface
  release_interface
  async_bulk_transfer
  handle_events
  cancel_transfer

FTD3 command transport
  create_pipe
  abort_pipe
  set_stream_pipe
  prepare_read_pipe
  prepare_write_pipe

N3DSXL device protocol
  device filter
  connect sequence
  SPI/config command sequence
  stream setup
  raw frame read
  async streaming
```

## 3.2 Tier 1: old 3DS

old 3DS は `usb_ds_3ds_capture.cpp` 系に対応する。

観測事項:

```text
old 3DS VID/PID: 0x16D0:0x06A3
interface: 0
endpoint: 2 | LIBUSB_ENDPOINT_IN
control vendor request timeout: 30ms
bulk timeout: 50ms
capture start request: 0x40
I2C/config request: 0x21
3D capable version threshold: 6
```

old 3DS と new 3DS XL は transport が異なる。

```text
new 3DS XL:
  FTDI VID/PID + product string filter
  command interface + bulk interface
  FTD3 command pipe
  async streaming 前提

old 3DS:
  0x16D0:0x06A3
  vendor request で capture start
  bulk IN endpoint から frame を読む
```

共通化するのは次に留める。

```text
- CaptureDevice base interface
- RawCapture metadata
- CaptureFrame data model
- RGB8 3DS screen layout decoder
- ndarray / Pillow adapters
```

---

# 4. Package Layout

初期構成案:

```text
ponkan/
├── __init__.py
├── capture.py
├── devices/
│   ├── __init__.py
│   ├── base.py
│   ├── n3dsxl_ftd3.py
│   └── old3ds_usb.py
├── transport/
│   ├── __init__.py
│   ├── libusb_backend.py
│   ├── libusb_async.py
│   ├── ftd3_pipe.py
│   └── legacy_usb.py
├── protocol/
│   ├── __init__.py
│   ├── sizes.py
│   ├── n3dsxl.py
│   ├── old3ds.py
│   └── layout_3ds.py
├── streaming/
│   ├── __init__.py
│   ├── engine.py
│   ├── buffers.py
│   ├── stats.py
│   └── policies.py
├── image/
│   ├── __init__.py
│   ├── frame.py
│   ├── pillow.py
│   └── colorspace.py
├── tools/
│   ├── list_devices.py
│   ├── probe_n3dsxl.py
│   ├── capture_raw.py
│   ├── stream_n3dsxl.py
│   └── raw_to_png.py
└── errors.py
```

責務:

```text
transport/libusb_backend.py:
  libusb の薄い wrapper。
  device enumeration, open, claim, control_transfer, bulk_transfer を担当する。

transport/libusb_async.py:
  libusb async transfer と event handling を担当する。
  callback 内では decode しない。

transport/ftd3_pipe.py:
  FTD3 command protocol を担当する。
  create/abort/set_stream/prepare_read/prepare_write を実装する。

protocol/n3dsxl.py:
  N3DSXL の connect sequence、SPI/config read、stream setup、raw capture read を担当する。

protocol/layout_3ds.py:
  raw RGB8 video buffer を top/bottom/top_right に分割・回転・整形する。

streaming/engine.py:
  raw transfer pool、decode worker、output queue、drop policy、stats を統合する。

image/frame.py:
  Python 利用者に返す CaptureFrame を定義する。
```

---

# 5. Dependencies

## 5.1 Hard dependencies

```text
numpy
libusb binding with low-level async transfer support
```

`numpy` は画像 buffer の標準表現として使う。

libusb binding は、少なくとも次を扱える必要がある。

```text
- device enumeration
- product string read
- configuration set
- interface claim/release
- control transfer
- bulk transfer
- async bulk transfer
- transfer callback
- event handling loop
- transfer cancellation
```

候補は `python-libusb1`。`pyusb` は同期 bulk 転送には使いやすいが、MVP に async transfer を含めるため第一候補にしない。

## 5.2 Optional dependencies

```text
Pillow
opencv-python
```

Pillow は `to_pillow()` が呼ばれたときだけ必要にする。OpenCV は hard dependency にしない。OpenCV 利用者には `numpy.ndarray` を返す。

---

# 6. Data Model

## 6.1 CaptureFrame

3DS capture では、利用者が欲しい単位は単一の長方形画像ではなく、上画面・下画面・必要なら 3D 右目画面である。Python 版では `CaptureFrame` を中心にする。

```python
from dataclasses import dataclass
from typing import Literal
import numpy as np

ColorSpace = Literal["RGB", "BGR"]
ScreenName = Literal["top", "bottom", "top_right"]

@dataclass(slots=True)
class CaptureFrame:
    top: np.ndarray               # shape: (240, 400, 3), dtype: uint8, RGB
    bottom: np.ndarray            # shape: (240, 320, 3), dtype: uint8, RGB
    top_right: np.ndarray | None  # shape: (240, 400, 3) if 3D, else None
    timestamp_ns: int | None
    source_model: str             # "new_3ds_xl" or "old_3ds"
    mode_3d: bool
    sequence: int | None = None
    colorspace: ColorSpace = "RGB"

    def to_ndarray(self, screen: ScreenName = "top", colorspace: ColorSpace = "RGB") -> np.ndarray:
        ...

    def to_pillow(self, screen: ScreenName = "top"):
        ...

    def to_mosaic(self, gap: int = 0) -> np.ndarray:
        ...
```

制約:

```text
frame.top.dtype == np.uint8
frame.bottom.dtype == np.uint8
frame.top.shape == (240, 400, 3)
frame.bottom.shape == (240, 320, 3)
frame.colorspace == "RGB"
```

OpenCV 互換出力は `colorspace="BGR"` で返す。内部標準は RGB。

## 6.2 RawCapture

実機調査、golden fixture、差分調査のために raw transfer を保持する。

```python
@dataclass(slots=True)
class RawCapture:
    model: str
    mode_3d: bool
    payload: bytes
    transferred: int
    video_size: int
    capture_size: int
    timestamp_ns: int | None
    sequence: int | None
    metadata: dict
```

`RawCapture` は通常 API の主役ではない。streaming 中の通常利用者には `CaptureFrame` を渡す。

## 6.3 Streaming types

MVP に async streaming を含めるため、raw buffer と decoded frame の寿命を明示する。

```python
from dataclasses import dataclass
from typing import Literal

DropPolicy = Literal["drop_oldest", "drop_newest", "block"]
CopyPolicy = Literal["copy_decoded_frame_before_release_raw_slot", "zero_copy_experimental"]

@dataclass(slots=True)
class RawFrameSlot:
    index: int
    buffer: bytearray
    view: memoryview
    in_use: bool = False
    submitted_ns: int | None = None
    completed_ns: int | None = None
    transferred: int = 0
    sequence: int | None = None

@dataclass(slots=True)
class RawFrameResult:
    slot_index: int
    view: memoryview
    transferred: int
    status: int
    completed_ns: int
    sequence: int

@dataclass(slots=True)
class StreamStats:
    submitted: int = 0
    completed: int = 0
    decoded: int = 0
    delivered: int = 0
    dropped_raw: int = 0
    dropped_decoded: int = 0
    usb_errors: int = 0
    decode_errors: int = 0
    cancelled: int = 0
    last_error: str | None = None
```

`RawFrameSlot.buffer` は `capture_size` 分を事前確保する。callback 内で新しい `bytes` を毎回作らず、`memoryview(buffer)[:transferred]` を後段へ渡す。

MVP の推奨値:

```text
raw_slots = 4 or 6
raw_slot_size = capture_size_2d
output_queue_size = 2
queue_full_policy = drop_oldest
copy_policy = copy_decoded_frame_before_release_raw_slot
```

`copy_policy` は最初の E2E では安全側に倒す。安定後に、buffer lifetime を厳密に管理して copy 削減を検討する。

---

# 7. new 3DS XL Raw Sizes

## 7.1 画面サイズ

```text
TOP_WIDTH_3DS = 400
BOT_WIDTH_3DS = 320
HEIGHT_3DS    = 240
```

2D raw video layout:

```text
input width  = 240
input height = 400 + 320 = 720
RGB8 bytes   = 240 * 720 * 3 = 518400
```

3D raw video layout:

```text
input width  = 240
input height = 400 + 320 + 400 = 1120
RGB8 bytes   = 240 * 1120 * 3 = 806400
```

raw layout は最終表示の向きと一致しない可能性が高い。単純な `reshape((720, 240, 3))` だけを最終画像とみなさない。

## 7.2 Capture struct 由来のサイズ

new 3DS XL capture struct は概ね次を含む。

```text
video_in: RGB83DSVideoInputData or RGB83DSVideoInputData_3D
audio_data: uint16_t[N3DSXL_SAMPLES_IN]
unused_buffer: 1024 bytes
error_buffer: 1024 bytes
```

`N3DSXL_SAMPLES_IN = 1096 * 16`。音声データは `uint16_t` 配列なので、バイト数は `1096 * 16 * 2 = 35072`。

`capture_size` は `sizeof(FTD3_3DSCaptureReceived)` / `sizeof(FTD3_3DSCaptureReceived_3D)` を 1024 byte 境界に切り下げる式を Python 側でも再現する。

初期計算値:

```text
2D:
  video_size = 518400
  audio_size = 35072
  struct_total_before_1024_floor = 555520
  capture_size_by_floor_1024 = 555008
  max_non_error_transferred = 553984

3D:
  video_size = 806400
  audio_size = 35072
  struct_total_before_1024_floor = 843520
  capture_size_by_floor_1024 = 842752
  max_non_error_transferred = 841728
```

実機 raw dump で検証する条件:

```text
- transferred >= video_size
- transferred <= capture_size
- payload 先頭の video_size bytes を decoder へ渡す
- error buffer 領域に入った疑いがある read は失敗として扱う
```

---

# 8. new 3DS XL Protocol Outline

## 8.1 Device filtering

Python 版は以下で device 候補を絞る。

```text
VID == 0x0403
PID in {0x601e, 0x601f, 0x602a, 0x602b, 0x602c, 0x602d, 0x602f}
USB product string is unreadable, or in {"N3DSXL", "N3DSXL.2"}
```

product string が読める場合、`N3DSXL` / `N3DSXL.2` でない device は対象外にする。product string を確認できない場合は、accepted VID/PID、`product_string_status=unreadable` の記録、実機 marker、人間の明示承認を safety boundary として扱う。

## 8.2 libusb setup

手順:

```text
1. open device
2. control IN probe
   - request = 3, value = 1, index = 0x8000, length = 4
   - request = 3, value = 1, index = 0x8400, length = 4
3. detach kernel driver for interface 0 and 1 if necessary
4. set configuration 1
5. claim interface 0
6. claim interface 1
7. create / abort pipe setup via FTD3 command pipe
```

## 8.3 FTD3 command pipe

```text
FTD3 command pipe id = 0x01
FTD3 command create pipe id = 0x82
FTD3 command bulk pipe id   = 0x01
command timeout = 500ms
```

Commands:

```text
abort pipe
read/write prepare
set stream pipe
create / destroy pipe
```

Python 側では `Ftd3Pipe` を作る。

```python
class Ftd3Pipe:
    def create_pipe(self) -> None: ...
    def abort_pipe(self, pipe: int) -> None: ...
    def set_stream_pipe(self, pipe: int, length: int) -> None: ...
    def read_pipe(self, pipe: int, length: int, timeout_ms: int) -> bytes: ...
    def write_pipe(self, pipe: int, payload: bytes, timeout_ms: int) -> int: ...
```

`read_pipe()` / `write_pipe()` は、単なる bulk 転送ではなく、事前に command pipe へ prepare command を送ってから BULK_IN / BULK_OUT を実行する。

## 8.4 N3DSXL connect sequence

概略:

```text
1. reconnect / open / claim
2. drain_data
3. close / reopen 相当の preemptive reset sequence
4. SPI access sequence
5. firmware / mode command
6. 3D config read
7. stream pipe setup
```

安全制約:

```text
- 未知の product string には送らない
- 未知の PID には送らない
- command 値を cc3dsfs 由来の範囲から増やさない
- dry-run / logging mode を用意する
- 最初の E2E では 2D mode をデフォルトにする
```

## 8.5 2D first

MVP では 2D capture を先に通す。

```text
MVP:
  requested_3d = False
  2D raw video size = 518400 bytes
  top + bottom を復元する

After MVP:
  requested_3d = True
  3D raw video size = 806400 bytes
  top_left + bottom + top_right を復元する
```

streaming 中の 3D mode 切替は MVP 外。stream 開始前に `mode_3d=False` を固定する。

---

# 9. Async High-Performance Streaming MVP

## 9.1 完了条件

MVP の完了条件は `continuous async streaming` とする。

bring-up gate:

```text
1. 1 フレーム取得
2. raw dump 保存
3. top / bottom ndarray 生成
4. PNG 出力
5. 手動目視確認
```

MVP acceptance:

```text
1. 複数の libusb async transfer を in-flight にする
2. raw buffer を事前確保して再利用する
3. callback 内では decode / Pillow 変換を行わない
4. decode worker へ raw completion を渡す
5. bounded output queue を通して利用者へ CaptureFrame を渡す
6. consumer が遅い場合は drop policy を適用する
7. stats で submitted / completed / decoded / delivered / dropped / errors を取得できる
8. stop 時に pending transfer を cancel し、interface を release する
```

## 9.2 採用する streaming 構造

`cc3dsfs` の libusb acquisition path は、複数 buffer を `in_use` で管理し、空き buffer に対して async read を開始し、callback で完了処理へ進める構成を持つ。Python 版では内部型名や mutex 実装は移植しないが、次の考え方は採用する。

```text
- capture_size 分の raw buffer を複数事前確保する
- libusb async transfer を複数 in-flight にする
- callback は軽く保つ
- transfer 完了順と sequence を記録する
- error 発生時は未完了 transfer を cancel する
- stop 要求時は cancel → drain → release を行う
```

## 9.3 Python streaming architecture

```text
LibusbEventThread
  ↓ callback
AsyncRawTransferEngine
  ↓ RawFrameResult queue
DecodeWorker
  ↓ CaptureFrame queue
Consumer API
  ├─ for frame in cap.frames()
  └─ async for frame in cap.frames_async()
```

### LibusbEventThread

libusb event handling を担当する専用 thread。`libusb_handle_events` 相当を回し、stop 要求時にすべての transfer cancel と join を行う。

libusb では非同期転送の callback は event handling を行う thread 上で呼ばれるため、この thread では blocking 処理や decode 処理を行わない。

### AsyncRawTransferEngine

責務:

```text
- RawFrameSlot を事前確保する
- N 個の transfer を submit する
- callback から完了 slot を queue へ積む
- 完了後、空き slot に次の transfer を submit する
- stop 時に cancel → drain → release を実行する
```

callback で行うこと:

```text
- transfer status を読む
- actual length を読む
- slot index / sequence / completed_ns を記録する
- completion queue へ通知する
```

callback で行わないこと:

```text
- ndarray decode
- Pillow 変換
- ファイル保存
- blocking queue put
- libusb synchronous API 呼び出し
```

### DecodeWorker

責務:

```text
- RawFrameResult から video 領域だけを取り出す
- layout_3ds decoder で top / bottom ndarray を作る
- CaptureFrame を output queue へ積む
- output queue が詰まった場合は drop policy を適用する
- 処理後に raw slot を再利用可能にする
```

MVP では 1 decode worker でよい。NumPy 変換が支配的なら後続で複数 worker 化または native extension を検討する。

## 9.4 Buffer lifetime

安全側の初期方針:

```text
copy_policy = copy_decoded_frame_before_release_raw_slot
```

理由:

```text
- np.frombuffer は元 buffer の寿命に依存する
- raw slot を再利用すると、consumer が保持している ndarray の内容が壊れる可能性がある
- MVP では copy 削減より正しさと shutdown 安全性を優先する
```

最適化候補:

```text
- decoded frame 用 buffer pool
- immutable frame ownership
- zero-copy experimental mode
- Cython / Rust / cffi による decoder 高速化
```

## 9.5 Public streaming API

同期利用者向け:

```python
from ponkan import open_capture

with open_capture(model="new_3ds_xl") as cap:
    for frame in cap.frames(max_queue=2, drop_policy="drop_oldest"):
        process(frame.top, frame.bottom)
```

asyncio 利用者向け:

```python
from ponkan import open_capture_async

async with await open_capture_async(model="new_3ds_xl") as cap:
    async for frame in cap.frames_async(max_queue=2, drop_policy="drop_oldest"):
        process(frame)
```

内部の USB 処理は thread + libusb callback でよい。`frames_async()` は asyncio Queue へ bridge する API として実装し、libusb event loop を asyncio に直結しない。

## 9.6 Drop policy

MVP ではリアルタイム処理を想定し、consumer が遅い場合は古い frame を捨てる。

```text
default output_queue_size = 2
default drop_policy = drop_oldest
```

理由:

```text
- capture stream を止めると USB 側の詰まり・timeout を誘発しやすい
- 利用者が見たいのは最新画面であり、古い frame を保持する価値は低い
- 録画用途は MVP 外
```

録画用途では `block` や大きな queue が必要になるが、MVP では扱わない。

## 9.7 Performance acceptance criteria

MVP の性能確認は、2D mode、no-op consumer、Pillow 変換なしで行う。

Hard gates:

```text
[ ] 2D mode で 60 秒 stream できる
[ ] USB transfer error で停止しない
[ ] callback thread が decode 処理で詰まらない
[ ] output queue が満杯になってもプロセスが固まらない
[ ] Ctrl-C / context manager exit で transfer cancel と interface release が完了する
[ ] stats を取得できる
```

初期性能目標:

```text
mode = 2D
stream_duration = 60 seconds
min_delivered_fps_noop_consumer = 50 fps
usb_errors = 0
process_shutdown_timeout = 2 seconds
raw_slots = 4 or 6
output_queue_size = 2
```

`min_delivered_fps_noop_consumer = 50 fps` は、Python 版が実用的な streaming 構造になっているかを判断する初期目標。実機・OS・USB controller・Python binding に依存するため、初回測定後にこの値を見直す。達しない場合は、stats と profile 結果を残し、binding 差し替えまたは native extension を検討する。

## 9.8 3D mode during streaming

MVP では streaming 中の 3D mode 切替を非対応にする。

```text
MVP:
  stream 開始前に mode_3d=False を固定する。
  実行中の mode 切替は UnsupportedOperation とする。

After MVP:
  pause_output → drain all buffers → 3D setup → resubmit transfers
```

---

# 10. Image Decoder

## 10.1 入力

```text
raw_video_2d: bytes-like object of length 518400
raw_video_3d: bytes-like object of length 806400
```

## 10.2 出力

2D:

```text
top:    np.ndarray shape=(240, 400, 3), dtype=np.uint8, RGB
bottom: np.ndarray shape=(240, 320, 3), dtype=np.uint8, RGB
```

3D:

```text
top_left:  np.ndarray shape=(240, 400, 3), dtype=np.uint8, RGB
bottom:    np.ndarray shape=(240, 320, 3), dtype=np.uint8, RGB
top_right: np.ndarray shape=(240, 400, 3), dtype=np.uint8, RGB
```

## 10.3 pending 事項

raw layout は `width=240` 側に流れているため、最終画像では転置・回転・flip が必要になる可能性が高い。

最初の decoder は以下を比較できるようにする。

```text
candidate_0: reshape only
candidate_1: reshape + transpose
candidate_2: reshape + rotate90
candidate_3: reshape + rotate90 + flip
```

`tools/raw_to_png.py` は candidate ごとに PNG を出せるようにする。手動目視で正しい候補を `decoder_version` として固定する。

---

# 11. Testing Strategy

## 11.1 テスト分類

```text
unit:
  libusb wrapper を mock し、command payload や size 計算を検証する。

characterization:
  cc3dsfs 由来の構造体サイズ、command sequence、raw fixture decode を固定する。

e2e_n3dsxl:
  実機 new 3DS XL capture board を使う。
  pytest marker: requires_n3dsxl

performance_n3dsxl:
  実機 new 3DS XL capture board を使う。
  async streaming の継続時間、fps、drop、error、shutdown を検証する。

manual_visual:
  出力 PNG を人間が確認する。
  初期段階では画像の向き・色順・画面分割の最終判定に使う。
```

## 11.2 E2E テストリスト

```text
[ ] list_devices returns at least one N3DSXL candidate
[ ] device candidate has VID 0x0403 and accepted PID
[ ] product string is N3DSXL or N3DSXL.2
[ ] open_n3dsxl can claim command interface 0 and bulk interface 1
[ ] ftd3 control probe returns without libusb error
[ ] ftd3 pipe create/abort sequence returns without libusb error
[ ] n3dsxl connect sequence completes in 2D default mode
[ ] set_stream_pipe for 2D capture size succeeds
[ ] one raw frame can be read
[ ] raw frame transferred length is >= 518400
[ ] raw frame is saved as .bin with metadata .json
[ ] raw frame decodes into top ndarray shape (240, 400, 3)
[ ] raw frame decodes into bottom ndarray shape (240, 320, 3)
[ ] dtype is uint8
[ ] PNG output can be generated for top and bottom screens
[ ] manual visual check confirms orientation and color order
[ ] async streaming can run for at least 60 seconds in 2D mode
[ ] streaming delivers >= 50 fps with no-op consumer in initial performance test
[ ] streaming stats report submitted/completed/decoded/delivered/dropped/errors
[ ] stopping stream cancels pending transfers and releases interfaces cleanly
```

## 11.3 Golden corpus

初回 E2E 成功後、次を保存する。

```text
tests/fixtures/n3dsxl/
  raw_2d_001.bin
  raw_2d_001.json
  top_001.png
  bottom_001.png
```

metadata 例:

```json
{
  "model": "new_3ds_xl",
  "product_string": "N3DSXL",
  "vid": "0x0403",
  "pid": "0x601f",
  "mode_3d": false,
  "transferred": 553984,
  "video_size": 518400,
  "capture_size": 555008,
  "decoder_version": 1,
  "manual_visual_status": "approved"
}
```

実機がなくても decoder の回帰テストを回せるようにする。

---

# 12. Error Handling and Shutdown

## 12.1 Exception hierarchy

```python
class CaptureError(Exception): ...
class DeviceNotFound(CaptureError): ...
class UnsupportedDevice(CaptureError): ...
class DeviceOpenError(CaptureError): ...
class InterfaceClaimError(CaptureError): ...
class Ftd3CommandError(CaptureError): ...
class TransferTimeout(CaptureError): ...
class TransferCancelled(CaptureError): ...
class TransferOverflow(CaptureError): ...
class DeviceDisconnected(CaptureError): ...
class DecodeError(CaptureError): ...
class UnsupportedOperation(CaptureError): ...
```

## 12.2 Cleanup invariant

`CaptureDevice.close()` は冪等にする。

```text
- streaming が動いていれば stop する
- pending transfer を cancel する
- cancellation callback を drain する
- claimed interface を release する
- handle を close する
- event thread を join する
```

例外発生時もこの順序を破らない。

---

# 13. Open Questions

```text
[ ] Python で使う libusb binding を確定する
    候補: python-libusb1, ctypes/cffi wrapper。
    FTD3 command/control/bulk 操作と libusb async transfer を低レベルに扱えることが必要。

[ ] Windows で new 3DS XL が libusb から見える状態にする手順
    FTD3XX vendor driver が入っている場合、libusb path と競合する可能性がある。

[ ] connect sequence のどこまでを再現するか
    drain/reopen/SPI/firmware/config read のうち、省略可能なものを実機で確認する。
    初期実装では cc3dsfs の手順を優先する。

[ ] 2D raw layout の正確な screen split / rotate / flip
    初回 raw dump と PNG 出力で確認する。

[ ] RGB/BGR 変換の扱い
    内部は RGB を標準にする。
    OpenCV 用には to_ndarray(colorspace="BGR") で返す。

[ ] async transfer binding の実装方式
    純 Python binding で足りるか、ctypes/cffi で libusb_transfer を直接扱う必要があるかを実機で確認する。

[ ] 初期性能目標の確定
    仮値は 2D / 60秒 / delivered >= 50 fps / usb_errors = 0。
    初回測定後に更新する。

[ ] audio_data の扱い
    MVP では無視するが、raw metadata には存在を記録する。
```

---

# 14. Source References

- `cc3dsfs` repository: https://github.com/Lorenzooone/cc3dsfs
- new 3DS XL FTD3 source directory: https://github.com/Lorenzooone/cc3dsfs/tree/main/source/CaptureDeviceSpecific/3DSCapture_FTD3
- FTD3 libusb acquisition: https://raw.githubusercontent.com/Lorenzooone/cc3dsfs/main/source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_libusb_acquisition.cpp
- FTD3 libusb communication: https://raw.githubusercontent.com/Lorenzooone/cc3dsfs/main/source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_libusb_comms.cpp
- FTD3 shared logic: https://raw.githubusercontent.com/Lorenzooone/cc3dsfs/main/source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_shared.cpp
- FTD3 compatibility layer: https://raw.githubusercontent.com/Lorenzooone/cc3dsfs/main/source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_compatibility.cpp
- hardware definitions: https://raw.githubusercontent.com/Lorenzooone/cc3dsfs/main/include/hw_defs.hpp
- capture structs: https://raw.githubusercontent.com/Lorenzooone/cc3dsfs/main/include/capture_structs.hpp
- libusb asynchronous I/O API: https://libusb.sourceforge.io/api-1.0/group__libusb__asyncio.html
- python-libusb1: https://github.com/vpelletier/python-libusb1
