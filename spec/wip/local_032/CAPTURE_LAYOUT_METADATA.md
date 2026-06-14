# Capture Layout Metadata 仕様書

更新日: 2026-06-14

## 1. 概要

### 1.1 目的

profile ごとの screen list、screen size、default composite、supported outputs、coordinate spaces、aspect / scale hints、colorspace default を public metadata として返し、利用側が device ごとの画面構成や座標変換を直書きしないようにする。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| screen | `top`、`bottom`、`top_right`、`main`、`touch` など、capture frame 内の論理画面。 |
| composite output | `both_vertical` など、複数 screen を 1 枚の ndarray に合成する layout。 |
| coordinate space | macro / touch / cursor が参照する座標系。 |
| aspect hint | preview 表示や HD aspect box 補正に必要な表示比率・scale 情報。 |
| layout metadata | image data を含まない、画面構成の public contract。 |

### 1.3 背景・問題

現行 `CaptureOutput` は N3DSXL の `TOP`、`BOTTOM`、`BOTH_VERTICAL` に固定されている。NyX は macro runtime へ 1 枚の BGR frame を渡すため `CaptureOutput.BOTH_VERTICAL` を使うが、profile が増える場合、screen 構成や coordinate transform を利用側が device ごとに持つと責務が破綻する。

この仕様では、実画像の decode や transform は変更しない。public metadata と既存 `CaptureOutput` / `CaptureFrame` の整合を固定する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| screen 構成 | docs / hardcoded shape から推測 | profile layout metadata から取得 |
| output validation | `CaptureOutput` enum 固定 | profile supported outputs と整合 |
| UI preview | 利用側が N3DSXL shape を直書き | screen size と composite size を参照 |
| coordinate transform | 利用側が device 固有で実装 | coordinate space metadata を参照 |
| profile 追加 | output set を別途設計 | layout metadata を追加するだけで判断可能 |

### 1.5 着手条件

- [ ] `local_027` の `CaptureProfile.screen_layout` が定義済みである。
- [ ] 現行 N3DSXL `CaptureFrame` shape と `CaptureOutput` の shape を確認する。
- [ ] layout metadata は画像 buffer を生成しない pure data API とする。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_032/CAPTURE_LAYOUT_METADATA.md` | 新規 | layout metadata の仕様を定義する。 |
| `src/ponkan/layouts.py` | 新規 | `CaptureLayout`、`ScreenInfo`、`CompositeOutputInfo` を定義する。 |
| `src/ponkan/profiles.py` | 修正 | profile と layout metadata を接続する。 |
| `src/ponkan/capture.py` | 修正 | `CaptureOutput` validation を layout metadata と整合させる。 |
| `src/ponkan/__init__.py` | 修正 | layout API を必要範囲で export する。 |
| `docs/api.md` | 修正 | layout metadata の利用例を追加する。 |
| `tests/unit/test_capture_layout_metadata.py` | 新規 | N3DSXL layout contract と output shape を検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| layout を取得する | `get_capture_layout("3ds_dual_screen")` | N3DSXL dual screen layout を返す | pure data |
| profile から layout を辿る | `get_capture_profile("n3dsxl").screen_layout` | layout id が取得できる | `local_027` と整合 |
| screen list | N3DSXL layout | `top` と `bottom` を含む | `top_right` は 3D unsupported の扱いを明記 |
| output set | N3DSXL layout | `top`、`bottom`、`both_vertical` | `CaptureOutput` と一致 |
| composite size | `both_vertical` | `(480, 400, 3)` | bottom centered |
| colorspace default | N3DSXL profile | profile default と一致 | `RGB` / `BGR` |
| unknown layout | typo | explicit error | fallback しない |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | N3DSXL layout は top/bottom screen metadata を持つ | contract | 3.1 | size 検証 |
| todo | `both_vertical` composite size が `(480, 400)` である | contract | 3.1 | existing `to_mosaic` と一致 |
| todo | `CaptureOutput` values が supported outputs と一致する | regression | 3.1 | enum / metadata drift 防止 |
| todo | profile layout id から layout を取得できる | integration | 3.1 | local_027 連携 |
| todo | unknown layout は error | edge | 3.1 | typo 検知 |

### 3.3 設計方針

layout metadata は「frame をどう返すか」の contract であり、decode algorithm や raw layout source order を表すものではない。cc3dsfs 由来の raw deinterleave は既存 decoder 仕様に残し、ここでは利用者が見る screen / output / coordinate の情報に限定する。

`CaptureOutput` は既存互換の enum として維持する。将来 profile 固有 output が増える場合、enum に共通 output を追加するか、string output を許容するかを別 Work Unit で決める。

## 4. 実装仕様

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScreenInfo:
    id: str
    display_name: str
    width: int
    height: int
    channels: int
    colorspace: str
    coordinate_space: str
    role: str


@dataclass(frozen=True, slots=True)
class CompositeOutputInfo:
    id: str
    display_name: str
    width: int
    height: int
    channels: int
    screens: tuple[str, ...]
    placement: str
    default: bool = False


@dataclass(frozen=True, slots=True)
class CaptureLayout:
    id: str
    display_name: str
    screens: tuple[ScreenInfo, ...]
    outputs: tuple[CompositeOutputInfo, ...]
    aspect_hints: dict[str, object]
```

N3DSXL layout:

| item | value |
| ---- | ----- |
| layout id | `3ds_dual_screen` |
| top screen | width 400, height 240, RGB |
| bottom screen | width 320, height 240, RGB |
| default composite | `both_vertical` |
| composite size | width 400, height 480 |
| placement | top above bottom, bottom centered |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| `get_capture_layout` | N3DSXL layout | `3ds_dual_screen` | top/bottom metadata |
| composite | both vertical | layout output | size `(400, 480)` |
| enum consistency | `CaptureOutput` | values | layout supported outputs と一致 |
| profile connection | `n3dsxl` | profile layout id | layout を取得できる |
| unknown | invalid id | `bogus` | error |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| docs example | preview size を metadata から作る | 実機なし | fixed constants に頼らない |
| read shape parity | metadata と `read()` shape の一致 | fake frame | top / bottom / both_vertical shape が一致 |

### 検証コマンド

```console
uv run pytest tests/unit/test_capture_layout_metadata.py
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

## 6. 実装チェックリスト

- [ ] layout metadata 型を定義する。
- [ ] N3DSXL `3ds_dual_screen` layout を実装する。
- [ ] profile metadata と layout metadata を接続する。
- [ ] `CaptureOutput` と supported outputs の drift を test する。
- [ ] docs/api に layout metadata の使い方を追加する。
- [ ] local gate を実行する。
