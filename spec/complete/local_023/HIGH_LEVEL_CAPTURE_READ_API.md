# High-Level Capture Read API 仕様書

更新日: 2026-06-10

## 1. 概要

### 1.1 目的

`py3dscapture` に `read()` で new 3DS XL の映像を取得できる高レベル API を追加し、利用者が USB backend、N3DSXL protocol、streaming engine を毎回手動で組み立てなくてよい状態にする。

OpenCV の `VideoCapture` は「開いて `read()` する」という利用感だけ参考にする。`get()` / `set()`、`CAP_PROP_*`、`grab()` / `retrieve()`、numeric property による設定など、OpenCV の API 形状は踏襲しない。取得対象は `CaptureOutput` enum で明示し、`read()` は選択された上画面、下画面、両画面縦並べの ndarray を返す。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| `open_capture()` | high-level capture reader を開く factory。device discovery、backend selection、protocol connect、streaming engine 作成をまとめる。 |
| `CaptureReader` | `read()`、`read_frame()`、`stats()`、`close()` を提供する高レベル reader。 |
| `CaptureConfig` | `open_capture()` に渡す明示的な設定。OpenCV property API ではなく、Python の keyword / dataclass として扱う。 |
| `CaptureOutput` | `read()` が返す画面 layout を表す enum。初期実装では `TOP`、`BOTTOM`、`BOTH_VERTICAL` を持つ。 |
| `read()` | 次の decoded frame から `CaptureOutput` で選ばれた RGB8 / BGR8 ndarray を返す主要 API。frame が timeout までに届かない場合は `None` を返す。 |
| `read_frame()` | 次の decoded `CaptureFrame` をそのまま返す domain API。上画面・下画面・metadata が必要な利用者向け。 |
| `CaptureFrame` | 既存の domain frame。`top`、`bottom`、`top_right`、timestamp、sequence を持つ。内部標準は RGB。 |
| colorspace | `read()` が返す ndarray の channel order。`RGB` または `BGR`。OpenCV 利用時は `BGR` を選べる。 |
| backend preference | backend 選択。`auto`、`libusb`、`d3xx`、`d3xx-native`。`d3xx-native` は opt-in で silent fallback しない。 |

### 1.3 背景・問題

現状の利用者向け surface は、`DeviceCandidate`、`N3DSXLProtocol`、`StreamingEngine`、D3XX backend、performance smoke helper を個別に組み立てる必要がある。これは bring-up や backend 開発には適しているが、通常利用で「capture board から画面を読む」には手順が露出しすぎている。

また、この project の frame は単一画像ではなく上画面・下画面を持つ。高レベル API では「どの画面が欲しいか」を明示できる必要がある。`read()` は `CaptureOutput` に従って ndarray を返し、3DS 固有情報を保持したい場合は `read_frame()` を使う。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| 最小利用コード | backend / protocol / engine を手動構築 | `with open_capture() as cap: image = cap.read()` で取得できる |
| API 形状 | low-level API が露出 | `read()`、`read_frame()`、`close()` 中心の薄い facade |
| 設定方法 | high-level API 未定義 | keyword / `CaptureConfig` / `CaptureOutput` で明示し、OpenCV property 方式は使わない |
| 画面選択 | caller が top / bottom / mosaic 処理を自前で組み立てる | enum で両画面縦並べ、上画面、下画面を選べる |
| 3DS 固有情報 | ndarray 変換時に top / bottom metadata を失いやすい | `read_frame()` で `CaptureFrame` を返し、上画面・下画面を保持する |
| OpenCV 接続 | caller が BGR 変換を自前で書く | `colorspace="BGR"` で接続しやすくする |
| safety | high-level API 未定義 | `open_capture()` を実機 command boundary とし、既存 VID/PID/product string/hardware approval 制約を維持する |
| cleanup | caller が engine / handle を個別に止める | context manager exit / `close()` で stop、cancel、drain、handle close まで行う |
| testability | 実機寄り helper に依存 | fake engine / fake opener で high-level behavior を unit test できる |

### 1.5 着手条件

- [x] `CaptureFrame` が top / bottom / mosaic / BGR 変換を提供している。
- [x] `StreamingEngine` が `start()`、`process_completed()`、`frames()`、`stop()`、`stats()` を提供している。
- [x] D3XX streaming backend が 2D mode の 60 秒 performance smoke を通している。
- [x] D3XX native backend が opt-in backend として実装済みで、default にはしない判断が記録済みである。
- [x] 実機 command の承認境界は `hardware_approved()` と `.codex` hook で保護されている。
- [x] Intent Delta: OpenCV の API 形状をまるごと模倣せず、`read()` で取得できる程度の高レベル API にする。
- [x] Intent Delta: 取得する画面を enum / 定数相当で指定できるようにする。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/complete/local_023/HIGH_LEVEL_CAPTURE_READ_API.md` | 完了済み | `read()` と `CaptureOutput` 中心の高レベル API 仕様、実装結果、gate 結果を記録する。 |
| `src/py3dscapture/capture.py` | 修正 | 既存 `CaptureSession` surface を踏まえ、`CaptureConfig`、`CaptureOutput`、`CaptureReader`、`open_capture()` を追加または整理する。 |
| `src/py3dscapture/__init__.py` | 修正 | `open_capture`、`CaptureConfig`、`CaptureOutput`、`CaptureReader` を public surface に追加する。 |
| `src/py3dscapture/errors.py` | 修正 | `DeviceNotFound` を追加する。timeout は recoverable state として `None` を返すため例外にしない。 |
| `tests/unit/test_high_level_capture_read_api.py` | 新規 | fake engine / fake opener で `read()`、`read_frame()`、output selection、timeout、cleanup を検証する。 |
| `tests/e2e/test_n3dsxl_high_level_capture_read_api.py` | 新規 | 実機 new 3DS XL で high-level API から 1 frame 以上取得できることを marker / approval gate 付きで検証する。 |
| `README.md` | 修正 | `open_capture()`、`CaptureOutput`、`read()` の最小使用例を追加する。 |
| `spec/complete/local_008/WORK_UNIT_INDEX.md` | 修正 | 実装完了時に `local_023` の状態と gate 結果を反映する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| reader を開く | `with open_capture() as cap:` | accepted N3DSXL candidate を選び、connect 済み streaming reader を返す | `open_capture()` が実機 command boundary |
| default 出力で読む | opened reader で `cap.read()` | 両画面縦並べ ndarray、timeout では `None` | default は `CaptureOutput.BOTH_VERTICAL` |
| 上画面を読む | `cap.read(output=CaptureOutput.TOP)` | shape `(240, 400, 3)` の ndarray | 上画面だけ |
| 下画面を読む | `cap.read(output=CaptureOutput.BOTTOM)` | shape `(240, 320, 3)` の ndarray | 下画面だけ |
| 両画面縦並べを読む | `cap.read(output=CaptureOutput.BOTH_VERTICAL)` | shape `(480, 400, 3)` の ndarray | 上画面の下に下画面を中央寄せ |
| BGR ndarray を読む | `cap.read(colorspace="BGR")` | BGR copy を返す | 内部 `CaptureFrame` は RGB のまま |
| domain frame を読む | `cap.read_frame()` | `CaptureFrame`、timeout では `None` | top / bottom 両方と metadata が必要な利用者向け |
| 最新 frame を優先する | queue に複数 decoded frame がある | `read()` / `read_frame()` は呼び出し時点で drain できる範囲の最新 frame を使う | display latency を増やさない |
| timeout を扱う | frame が timeout までに届かない | `None` を返す | 通常の read miss を例外にしない |
| stats を見る | streaming 後に `cap.stats()` | `StreamStats` snapshot を返す | diagnostic。設定 API にはしない |
| close する | `cap.close()` を複数回呼ぶ | 2 回目以降は no-op | context manager exit でも呼ぶ |
| source を指定する | `open_capture(source=0)` or `source="new_3ds_xl"` | 最初の accepted N3DSXL candidate を開く | 初期実装は 1 device 想定 |
| backend を指定する | `backend="auto"` / `"d3xx"` / `"d3xx-native"` | 指定に従って backend を選ぶ | `d3xx-native` は silent fallback しない |
| 3D mode を要求する | `mode_3d=True` | `UnsupportedOperation` | MVP 外 |
| OpenCV property を使う | `cap.get(...)` / `cap.set(...)` | API として提供しない | Intent Delta により非対象 |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | `open_capture()` は fake opener で `CaptureReader` を返す | new behavior | 3.1 | `tests/unit/test_high_level_capture_read_api.py` |
| green | `CaptureReader.read_frame()` は fake engine の `CaptureFrame` を返す | new behavior | 3.1 | domain API |
| green | `CaptureReader.read()` は default で両画面縦並べ ndarray を返す | new behavior | 3.1 | 主要 API |
| green | frame がない場合、`read()` / `read_frame()` は timeout 後 `None` を返す | edge | 3.1 | recoverable state |
| green | `read()` / `read_frame()` は queued frames の最新 frame を使う | behavior | 3.1 | latency 回避 |
| green | `read(output=CaptureOutput.TOP)` は top ndarray を返す | new behavior | 3.1 | shape `(240, 400, 3)` |
| green | `read(output=CaptureOutput.BOTTOM)` は bottom ndarray を返す | new behavior | 3.1 | shape `(240, 320, 3)` |
| green | `read(output=CaptureOutput.BOTH_VERTICAL)` は縦並べ ndarray を返す | new behavior | 3.1 | shape `(480, 400, 3)` |
| green | `read(colorspace="BGR")` は channel order を変換した copy を返す | compatibility | 3.1 | original frame は RGB のまま |
| green | invalid output は `ValueError` | edge | 3.1 | enum validation |
| green | backend hard error は `CaptureError` 系を raise する | error | 3.1 | error を握りつぶさない |
| green | context manager exit は `close()` を呼ぶ | cleanup | 3.1 | idempotent |
| green | `close()` は engine `stop()` と backend release を 1 回だけ実行する | cleanup | 3.1 | double close |
| green | `mode_3d=True` は `UnsupportedOperation` | scope | 3.1 | MVP 外 |
| green | explicit `d3xx-native` は unavailable 時に fallback しない | safety | 3.1 | opt-in backend |
| green | OpenCV property API を public surface に追加しない | design guard | 3.1 | `get` / `set` / `CAP_PROP_*` 非対象 |
| green | 実機 high-level API で 1 frame 以上取得できる | hardware-gated | 5 | `tests/e2e/test_n3dsxl_high_level_capture_read_api.py` |

### 3.3 設計方針

高レベル API は「設定可能な動画 capture object」ではなく、「new 3DS XL capture board を開いて、指定した画面 layout を読む reader」として設計する。OpenCV 風の property layer を入れないことで、device 固有の制約、backend 選択、queue policy、画面 layout を明示的な Python keyword / config / enum に閉じ込める。

API は次の形を基本にする。

```python
from py3dscapture import CaptureOutput, open_capture

with open_capture(output=CaptureOutput.BOTH_VERTICAL) as cap:
    image = cap.read()
    if image is not None:
        consume(image)
```

上画面だけ欲しい場合。

```python
from py3dscapture import CaptureOutput, open_capture

with open_capture() as cap:
    top = cap.read(output=CaptureOutput.TOP)
```

3DS 固有の `CaptureFrame` が必要な場合。

```python
from py3dscapture import open_capture

with open_capture() as cap:
    frame = cap.read_frame()
    if frame is not None:
        top = frame.top
        bottom = frame.bottom
```

初期 default は次にする。

| 設定 | 既定値 | 理由 |
| ---- | ------ | ---- |
| `source` | `0` | 最初の accepted N3DSXL candidate |
| `model` | `"new_3ds_xl"` | 初期対象 device |
| `backend` | `"auto"` | 実装時点の安定 backend resolver に任せる |
| `mode_3d` | `False` | MVP は 2D |
| `output` | `CaptureOutput.BOTH_VERTICAL` | default `read()` で上下画面を失わない |
| `colorspace` | `"RGB"` | 既存 `CaptureFrame` と package 内部標準に合わせる |
| `raw_slots` | `2` | 既存 D3XX low-latency default |
| `output_queue_size` | `2` | real-time 表示向け |
| `drop_policy` | `"drop_oldest"` | consumer 遅延時は最新画面を優先 |
| `poll_interval` | `0.004` | 既存 D3XX timing smoke の default |
| `read_timeout` | `1.0` | read を無限待ちにしない |

### 3.4 Output Layout

| `CaptureOutput` | value | shape | 配置 |
| --------------- | ----- | ----- | ---- |
| `TOP` | `"top"` | `(240, 400, 3)` | 上画面のみ |
| `BOTTOM` | `"bottom"` | `(240, 320, 3)` | 下画面のみ |
| `BOTH_VERTICAL` | `"both_vertical"` | `(480, 400, 3)` | 上画面の下に下画面を中央寄せ |

`BOTH_VERTICAL` は既存 `CaptureFrame.to_mosaic(gap=0)` と同じ layout とする。横並べは既存 helper がないため初期実装から外し、必要が出たら別 Work Unit で `CaptureOutput.BOTH_HORIZONTAL` と合成 helper を追加する。gap / padding / scaling は初期実装では扱わない。

### 3.5 State Machine

```text
OPENING
  - open_capture() 内で device identity guard、protocol connect、engine 作成を行う
  - accepted device に N3DSXL command を送る可能性がある

OPEN
  - CaptureReader が active
  - read() / read_frame() が streaming engine を開始または poll できる

CLOSED
  - engine.stop()、backend release、handle close 済み
  - close() は idempotent
```

constructor で未 open object を作る API は初期必須にしない。必要なら実装上 `CaptureReader` の内部 constructor は存在してよいが、public entry point は `open_capture()` を優先する。

### 3.6 実機安全制約

High-level API は safety boundary を緩めない。

```text
- VID/PID が accepted list にない device には N3DSXL command を送らない。
- product string が読める場合、N3DSXL / N3DSXL.2 以外には N3DSXL command を送らない。
- product string が unreadable の場合、既存 policy に従い metadata と marker / approval を安全境界にする。
- 実機 test には @pytest.mark.requires_n3dsxl を付ける。
- performance test には @pytest.mark.performance も付ける。
- CI では実機 test を実行しない。
- `open_capture()` / hardware E2E は PONKAN_HARDWARE_APPROVED=1 なしで実行しない。
- callback 内で decode、Pillow 変換、blocking queue put、同期 USB API 呼び出しを行わない。
- shutdown では engine.stop() 経由で cancel、drain、release、handle close を完了する。
```

## 4. 実装仕様

### 4.1 Public Types

```python
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from py3dscapture.image.frame import CaptureFrame, ColorSpace, RGB8Array
from py3dscapture.streaming.policies import DropPolicy
from py3dscapture.streaming.stats import StreamStats

CaptureSource = int | str
CaptureBackend = Literal["auto", "libusb", "d3xx", "d3xx-native"]


class CaptureOutput(StrEnum):
    TOP = "top"
    BOTTOM = "bottom"
    BOTH_VERTICAL = "both_vertical"


@dataclass(slots=True)
class CaptureConfig:
    source: CaptureSource = 0
    model: Literal["new_3ds_xl"] = "new_3ds_xl"
    backend: CaptureBackend = "auto"
    mode_3d: bool = False
    output: CaptureOutput = CaptureOutput.BOTH_VERTICAL
    colorspace: ColorSpace = "RGB"
    raw_slots: int = 2
    output_queue_size: int = 2
    drop_policy: DropPolicy = "drop_oldest"
    poll_interval: float = 0.004
    read_timeout: float | None = 1.0
    collect_timing: bool = False
```

`CaptureOutput` は `StrEnum` として定義し、debug log や JSON artifact に value を出しやすくする。公開 API では enum member を使うことを推奨し、文字列の直接指定を受けるかどうかは実装時の validation helper で固定する。

Validation:

| field | 条件 | 失敗時 |
| ----- | ---- | ------ |
| `source` | `0` または `"new_3ds_xl"` を初期対応 | `UnsupportedOperation` |
| `model` | `"new_3ds_xl"` のみ | `UnsupportedOperation` |
| `backend` | literal のいずれか | `ValueError` |
| `mode_3d` | `False` のみ | `UnsupportedOperation` |
| `output` | `CaptureOutput` のいずれか | `ValueError` |
| `colorspace` | `RGB/BGR` | `ValueError` |
| `raw_slots` | `> 0` | `ValueError` |
| `output_queue_size` | `> 0` | `ValueError` |
| `poll_interval` | `> 0` | `ValueError` |
| `read_timeout` | `None` または `>= 0` | `ValueError` |

### 4.2 Public Functions and Class

```python
def open_capture(
    source: CaptureSource = 0,
    *,
    config: CaptureConfig | None = None,
    backend: CaptureBackend | None = None,
    output: CaptureOutput | None = None,
    colorspace: ColorSpace | None = None,
    read_timeout: float | None = None,
) -> CaptureReader:
    ...


class CaptureReader:
    def read(
        self,
        *,
        output: CaptureOutput | None = None,
        colorspace: ColorSpace | None = None,
        timeout: float | None = None,
    ) -> RGB8Array | None:
        ...

    def read_frame(self, *, timeout: float | None = None) -> CaptureFrame | None: ...
    def stats(self) -> StreamStats: ...
    def close(self) -> None: ...

    def __enter__(self) -> "CaptureReader": ...
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...
```

`open_capture()` の引数は `CaptureConfig` をベースにしつつ、よく使う `source`、`backend`、`output`、`colorspace`、`read_timeout` だけを keyword override できるようにする。細かい tuning は `CaptureConfig` に寄せ、OpenCV property API は提供しない。

### 4.3 Read Semantics

`read_frame()` は次を行う。

```text
1. reader が closed なら None を返す。
2. engine が未 start なら start する。
3. timeout まで engine.process_completed(limit=8) と engine.frames() を poll する。
4. queued frames が複数あれば最新 frame を返す。
5. timeout まで frame がなければ None を返す。
6. backend hard error は CaptureError 系として呼び出し元へ伝播する。
```

`read()` は `read_frame()` で得た `CaptureFrame` から selected output の ndarray を作る。

```text
- output=TOP: frame.to_ndarray("top", colorspace)
- output=BOTTOM: frame.to_ndarray("bottom", colorspace)
- output=BOTH_VERTICAL: frame.to_mosaic(gap=0) を作り、必要なら BGR copy に変換する
```

`read()` が selected ndarray を返し、`read_frame()` が `CaptureFrame` を返す理由:

```text
- high-level API の主要用途では、選んだ画面 layout をすぐ画像処理へ渡したい。
- 画面選択は enum で明示でき、OpenCV property layer を持ち込まずに済む。
- 3DS 固有の top / bottom / timestamp / sequence が必要な利用者は read_frame() を使える。
```

### 4.4 Backend Opening

High-level opener は次の責務を持つ。

```text
1. source/model/backend config を検証する。
2. accepted N3DSXL candidate を列挙する。
3. backend preference に従って transport を開く。
4. N3DSXLProtocol.connect(mode_3d=False) を実行する。
5. StreamingEngine を作る。
6. CaptureReader に engine、identity metadata、backend kind、close owner を渡す。
```

`backend="auto"` の初期方針:

```text
- libusb が使える場合は libusb path を優先する。
- libusb open が driver/backend mismatch の場合だけ D3XX fallback を検討する。
- 現在安定している Windows 実機 path が D3XX の場合、実装 Work Unit で default resolver を現状の e2e helper と矛盾しない形にする。
- d3xx-native は明示指定された場合だけ使う。
```

この仕様は backend resolver の詳細を固定しすぎない。実装時点の既存 hardware gate と安定 backend に合わせ、unit test では fake opener で high-level API behavior を先に固定する。

### 4.5 Non-goals

```text
- OpenCV の VideoCapture class 名や API 形状の模倣
- get() / set() / CAP_PROP_* / numeric property layer
- grab() / retrieve() の公開
- GUI、audio、recording、old DS、old 3DS、非 N3DSXL device
- streaming 中の 3D mode 切替
- d3xx-native の default 化
- 2D MVP での top_right high-level output
- 初期実装での both horizontal output
- output layout の gap / scaling / crop / resize 設定
```

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| `open_capture()` | fake opener integration | default config | `CaptureReader` が返る |
| `read_frame()` | domain frame delivery | fake engine with 1 frame | `CaptureFrame` が返る |
| `read_frame()` | timeout | fake engine empty | `None` が返る |
| `read_frame()` | latest frame | fake engine with multiple frames | 最新 sequence の frame が返る |
| `read()` | default output | fake frame | `BOTH_VERTICAL` shape `(480, 400, 3)` |
| `read()` | top output | `CaptureOutput.TOP` | shape `(240, 400, 3)` |
| `read()` | bottom output | `CaptureOutput.BOTTOM` | shape `(240, 320, 3)` |
| `read()` | vertical output | `CaptureOutput.BOTH_VERTICAL` | shape `(480, 400, 3)`、bottom centered |
| `read()` | BGR conversion | RGB sentinel pixel | channel order reversed |
| `read()` | invalid output | invalid value | `ValueError` |
| error propagation | backend error | fake engine raises `CaptureError` | caller へ伝播 |
| cleanup | context manager | fake engine / owner | exit で close |
| cleanup | idempotent close | close twice | stop/release は 1 回 |
| design guard | OpenCV property API 非追加 | public module | `CAP_PROP_*`、`get`、`set` を追加しない |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| high-level D3XX smoke | `open_capture().read()` で 1 frame 取得 | 実機、D3XX driver、承認済み command | ndarray が返る |
| high-level output smoke | `CaptureOutput.TOP/BOTTOM/BOTH_VERTICAL` を指定して読む | 実機、承認済み command | 各 shape が一致する |
| high-level read_frame smoke | `read_frame()` で `CaptureFrame` を取得 | 実機、承認済み command | top / bottom shape が一致する |
| release cleanup | context exit | 実機、承認済み command | shutdown <= 2 sec、usb_errors == 0 |
| native opt-in smoke | `backend="d3xx-native"` | 実機、native backend available、承認済み command | success なら artifact、unavailable なら explicit skip/error |

### 検証コマンド

Local gate:

```console
uv run pytest tests/unit/test_high_level_capture_read_api.py
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
git diff --check
```

Hardware-gated gate:

```console
$env:PONKAN_RUN_N3DSXL = "1"
$env:PONKAN_HARDWARE_APPROVED = "1"
$env:PONKAN_N3DSXL_DRIVER_SERVICE = "FTDIBUS3"
uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_high_level_capture_read_api.py
```

実機 gate は人間承認なしでは実行しない。

## 6. 実装チェックリスト

- [x] `CaptureOutput` enum を実装する。
- [x] `CaptureConfig` と validation を実装する。
- [x] `CaptureReader` と `open_capture()` を実装する。
- [x] fake engine を使って `read_frame()` の TDD item を green にする。
- [x] timeout / latest frame / error propagation の TDD item を green にする。
- [x] `read()` の output / colorspace TDD item を green にする。
- [x] context manager と idempotent close の TDD item を green にする。
- [x] OpenCV property API を追加していないことを design guard で確認する。
- [x] high-level opener を実装し、既存 N3DSXL safety boundary を通す。
- [x] `__init__.py` の public export を更新する。
- [x] README に `open_capture()` / `CaptureOutput` / `read()` の最小使用例を追加する。
- [x] local gate を実行する。
- [x] 承認後に実機 high-level E2E を実行する。
- [x] gate 結果をこの仕様と `WORK_UNIT_INDEX.md` に反映し、complete へ移動する。

## 7. 実装結果

### 7.1 実装サマリ

`src/py3dscapture/capture.py` に `CaptureOutput`、`CaptureConfig`、`CaptureReader`、`open_capture()` を追加した。`CaptureReader.read_frame()` は `StreamingEngine.start()` を lazy に呼び、`process_completed(limit=8)` と decoded frame queue を polling して、drain できる範囲の最新 `CaptureFrame` を返す。timeout では `None` を返し、backend hard error は握りつぶさない。

`CaptureReader.read()` は `CaptureOutput.TOP`、`CaptureOutput.BOTTOM`、`CaptureOutput.BOTH_VERTICAL` を扱い、`BOTH_VERTICAL` は既存 `CaptureFrame.to_mosaic(gap=0)` と同じ layout にした。`colorspace="BGR"` では copy を返し、内部 `CaptureFrame` は RGB のまま保持する。

high-level opener は現行の安定実機経路に合わせ、`auto` / `d3xx` は `D3xxBackend`、`N3DSXLProtocol.connect(mode_3d=False)`、`StreamingEngine(D3xxAsyncBackend(...))` を組み立てる。`d3xx-native` は opt-in の `D3xxNativeFastPathBackend` を使い、作成失敗時に D3XX sequential backend へ silent fallback しない。`libusb` は high-level async backend が未実装のため `UnsupportedOperation` として明示的に拒否する。

### 7.2 Gate Results

| Gate | 結果 | Evidence |
| ---- | ---- | -------- |
| Target unit | pass | `uv run pytest tests\unit\test_high_level_capture_read_api.py -q`: 17 passed。 |
| Package surface | pass | `uv run pytest tests\unit\test_package.py -q`: 1 passed。 |
| Unit full | pass | `uv run pytest tests\unit`: 120 passed。 |
| E2E marker safety | pass / skipped | `uv run pytest tests\e2e\test_n3dsxl_high_level_capture_read_api.py -q`: 1 skipped。`PONKAN_RUN_N3DSXL` 未設定のため実機 command は未実行。 |
| Hardware high-level E2E | pass | 2026-06-10: user approval 後、`PONKAN_RUN_N3DSXL=1`、`PONKAN_HARDWARE_APPROVED=1`、`PONKAN_N3DSXL_DRIVER_SERVICE=FTDIBUS3` で `uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_high_level_capture_read_api.py -q`: 1 passed。 |
| Hardware artifact | pass | `artifacts\n3dsxl\20260610-010730\pytest-high-level-read-api\test_n3dsxl_high_level_capture0\n3dsxl\high-level-read-api\read_stats.json`: `top_shape=[240, 400, 3]`, `bottom_shape=[240, 320, 3]`, `both_shape=[480, 400, 3]`, `usb_errors=0`, `decode_errors=0`。 |
| Static | pass | `uv run ruff format --check .`、`uv run ruff check .`、`uv run ty check --no-progress`。 |

### 7.3 Hardware Gate Result

実機 high-level E2E は、ユーザ承認後に次の scope で実行した。

```console
$env:PONKAN_RUN_N3DSXL = "1"
$env:PONKAN_HARDWARE_APPROVED = "1"
$env:PONKAN_N3DSXL_DRIVER_SERVICE = "FTDIBUS3"
uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_high_level_capture_read_api.py
```

この gate の command scope は `open_capture(backend="d3xx")` で accepted N3DSXL candidate を開き、`N3DSXLProtocol.connect(mode_3d=False)` と D3XX streaming read を使って `read_frame()` / `read()` の shape と stats を確認すること。`read_stats.json` では top / bottom / both vertical の shape が仕様と一致し、`usb_errors=0`、`decode_errors=0` を確認した。shutdown は context manager exit から `engine.stop()` と backend release を通る。
