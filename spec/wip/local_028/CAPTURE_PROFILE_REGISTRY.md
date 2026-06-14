# Capture Profile Registry 仕様書

更新日: 2026-06-14

## 1. 概要

### 1.1 目的

`ponkan` に実装済み capture profile の公開 registry を追加し、利用側が N3DSXL 固定の `CaptureConfig` を直接解釈せずに、device family、support status、default output、default colorspace、native FPS、layout 種別を取得できるようにする。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| capture profile | `n3dsxl` など、device family と capture contract を表す public metadata。 |
| profile id | 利用者が設定として保存できる安定 ID。初期値は `n3dsxl`。 |
| support status | runtime registry に含まれる profile の実装・検証状態。初期 contract は `stable`、`experimental` のいずれか。 |
| family | `3ds` など、NyX などの利用側 UI が大分類として扱える device family。 |
| provider | profile を提供する実装主体。ここでは `ponkan-python`。 |
| native FPS | profile の実機 capture が自然に供給する FPS。N3DSXL では約 59.8fps の観測値を初期 metadata とする。 |

### 1.3 背景・問題

現行公開 API は `open_capture()`、`CaptureConfig`、`CaptureOutput`、`CaptureReader`、`capture_sizes()` を中心に、`new_3ds_xl` だけを暗黙的に扱う。Project NyX のような利用側が将来 old 3DS や別 profile を扱う場合、GUI 側に device family や support status の知識を重複実装すると、profile 追加のたびに設定と分岐が増殖する。

この仕様では、N3DSXL 以外を実装しない。runtime registry は「現在開ける、または実装済みで実験扱いの profile」だけを返す public contract とする。未実装 device の計画や source audit は `local_033` の roadmap で扱い、runtime API には混ぜない。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| profile 発見 | 利用側が docs / import surface / config を推測する | `list_capture_profiles()` で取得できる |
| N3DSXL 表示判断 | 利用側が `new_3ds_xl` と package availability を独自解釈する | `support_status` と `supported_outputs` で UI 表示を判断できる |
| 将来 profile | 利用側設定に device 固有項目が増える | profile metadata と layout / capability contract に寄せる |
| unsupported / future device | registry と roadmap の境界が曖昧 | runtime registry には含めず、`local_033` の source audit gate で扱う |
| 実機安全 | registry 呼び出しから command 送信の有無が曖昧 | registry は USB device open も N3DSXL command 送信もしない |

### 1.5 着手条件

- [ ] 現行 `ponkan.__init__` の public export と `docs/api.md` を確認する。
- [ ] N3DSXL の現行 default output、colorspace、backend、layout、native FPS 観測値を既存 complete spec から確認する。
- [ ] profile metadata は実機 command を送らない pure data API として設計する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_028/CAPTURE_PROFILE_REGISTRY.md` | 新規 | profile registry の public contract を定義する。 |
| `src/ponkan/profiles.py` | 新規 | `CaptureProfile`、`SupportStatus`、`list_capture_profiles()`、`get_capture_profile()` を定義する。 |
| `src/ponkan/__init__.py` | 修正 | profile registry API を package root から export する。 |
| `docs/api.md` | 修正 | profile registry と support status の利用例を追記する。 |
| `tests/unit/test_capture_profiles.py` | 新規 | registry の pure data behavior と alias 解決を検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| profile を列挙する | `list_capture_profiles()` | `CaptureProfile` の tuple を返す | USB device enumeration は行わない |
| N3DSXL profile を取得する | `get_capture_profile("n3dsxl")` | `id="n3dsxl"` の profile を返す | 初期 stable target |
| alias を解決する | `get_capture_profile("new_3ds_xl")` | `n3dsxl` profile を返す | 既存 `CaptureConfig.model` からの移行用 |
| 未知 profile を扱う | `get_capture_profile("classic_ds")` | `UnknownCaptureProfile` または `CaptureError` を返す | source audit 前に予約しない |
| status で UI 判断する | `support_status in {"stable", "experimental"}` | 通常 UI に表示できる | runtime registry はこの 2 状態だけ返す |
| future device を分離する | `old3ds` / `classic_ds` / `optimize` など | `list_capture_profiles()` には含めない | `local_033` の roadmap / docs で扱う |
| 実機 command を送らない | registry API 呼び出し | USB open / command / hardware approval は不要 | safety boundary |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | `list_capture_profiles()` は immutable tuple を返す | new behavior | 3.1 | 呼び出しごとに破壊的変更されない |
| todo | `n3dsxl` profile の必須 metadata が仕様通りである | contract | 3.1 | id、family、model、status、outputs |
| todo | `new_3ds_xl` alias は `n3dsxl` に解決される | compatibility | 3.1 | 既存 API 用語との接続 |
| todo | unknown profile は明示的な error を返す | edge | 3.1 | 文字列解析不要 |
| todo | registry API は backend import や device open を行わない | safety | 3.1 | monkeypatch / fake import で確認 |
| todo | package root から profile API を import できる | public surface | 2 | `from ponkan import list_capture_profiles` |

### 3.3 設計方針

profile registry は low-level backend や device enumeration から独立した pure metadata とする。呼び出しは設定画面や CLI startup でも安全に実行でき、N3DSXL command を送らない。

`support_status` は UI 表示のための実装状態であり、実機の現在接続状態ではない。driver や backend runtime の状態は `local_029` の backend capability API で扱う。

`old3ds`、`classic_ds`、Optimize / Nisetro / IS 系 device は初期 registry に追加しない。これらの扱いは `local_033` の source audit gate を通った後に、別 Work Unit で runtime registry へ追加するかを判断する。

## 4. 実装仕様

```python
from dataclasses import dataclass
from typing import Literal

SupportStatus = Literal["stable", "experimental"]


@dataclass(frozen=True, slots=True)
class CaptureProfile:
    id: str
    display_name: str
    model: str
    family: str
    provider: str
    support_status: SupportStatus
    default_output: str
    default_colorspace: str
    native_fps: float | None
    screen_layout: str
    supported_outputs: tuple[str, ...]
    supports_3d: bool
    supports_audio: bool
    supports_recording: bool
    aliases: tuple[str, ...] = ()
```

初期 profile:

| profile id | status | 根拠 | 備考 |
| ---------- | ------ | ---- | ---- |
| `n3dsxl` | `stable` | high-level read API、D3XX streaming、performance gate 済み | default output は `both_vertical` |

Public API:

```python
def list_capture_profiles() -> tuple[CaptureProfile, ...]:
    ...


def get_capture_profile(profile: str) -> CaptureProfile:
    ...
```

`list_capture_profiles()` は実装済み profile だけを返す。未実装 device を通常 UI から隠すための diagnostics registry はこの仕様では作らない。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| `list_capture_profiles` | N3DSXL profile を返す | default | `n3dsxl` が含まれる |
| `get_capture_profile` | exact id 解決 | `n3dsxl` | profile を返す |
| `get_capture_profile` | alias 解決 | `new_3ds_xl` | `id == "n3dsxl"` |
| future profile filter | 未実装 profile の扱い | default | `old3ds` / `classic_ds` は返らない |
| safety | 副作用なし | backend import monkeypatch | import / open されない |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| API docs example | docs の import 例が成立する | 実機なし | profile 一覧を取得できる |
| NyX-style filtering | `stable` / `experimental` だけ抽出する | 実機なし | N3DSXL だけ通常候補になる |

### 検証コマンド

```console
uv run pytest tests/unit/test_capture_profiles.py
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

## 6. 実装チェックリスト

- [ ] `CaptureProfile` と `SupportStatus` を定義する。
- [ ] N3DSXL profile の metadata を固定する。
- [ ] future / unsupported device を runtime registry に混ぜないことを固定する。
- [ ] `list_capture_profiles()` と `get_capture_profile()` を実装する。
- [ ] package root export を追加する。
- [ ] docs/api に利用例と UI filtering 指針を追加する。
- [ ] unit test と static gate を実行する。
