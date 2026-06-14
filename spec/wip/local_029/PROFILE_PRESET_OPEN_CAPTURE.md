# Profile Preset Open Capture 仕様書

更新日: 2026-06-14

## 1. 概要

### 1.1 目的

`CaptureConfig.for_profile()` と `open_capture(profile=...)` を追加し、利用側が raw slots、queue size、drop policy、poll interval などの低レベル tuning を通常設定として持たずに、profile default から high-level reader を開けるようにする。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| profile preset | `CaptureProfile` の default と low-level tuning default から作る `CaptureConfig`。 |
| high-level open | `open_capture(profile="n3dsxl", output=..., colorspace=...)` のように、profile id と利用側に必要な少数の設定だけで reader を開く API。 |
| low-level tuning | `raw_slots`、`output_queue_size`、`drop_policy`、`poll_interval`、`read_timeout`、`collect_timing`。 |
| target FPS | delivery / pacing の目標 FPS。実際の pacing 実装は `local_030` で扱う。 |

### 1.3 背景・問題

現行 `CaptureConfig` は N3DSXL に必要な low-level knobs を直接持つ。Project NyX のような利用側は通常 GUI にこれらを出さず、`profile`、`backend preference`、`output`、`colorspace`、`capture_fps` 程度を扱いたい。profile が増えたときも、利用側が device 固有 default を再実装しないように、ponkan-python 側に preset 解決を置く。

この仕様は profile-driven open の contract を固定する。`target_fps` の実効 pacing と stats は `local_030` に分離する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| open API | `source` / `model` と low-level config が中心 | `profile` id から default を解決できる |
| 利用側設定 | raw slots や queue policy も知る必要がある | high-level 設定だけを保存できる |
| profile 追加 | 利用側 adapter の分岐が増える | preset default を ponkan-python 側に寄せる |
| default 整合 | docs / tests / config が別々 | `CaptureProfile` と `CaptureConfig.for_profile()` で一致させる |

### 1.5 着手条件

- [ ] `local_027` の profile registry が利用可能である。
- [ ] `local_028` の backend resolver と default backend policy が確認済みである。
- [ ] 現行 `open_capture()` の behavior と実機 safety boundary を維持する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_029/PROFILE_PRESET_OPEN_CAPTURE.md` | 新規 | profile preset と simplified open API の仕様を定義する。 |
| `src/ponkan/capture.py` | 修正 | `CaptureConfig.for_profile()`、`profile` / `target_fps` 引数、profile default 解決を追加する。 |
| `src/ponkan/profiles.py` | 修正 | profile default と `CaptureConfig` default の整合を取る。 |
| `src/ponkan/__init__.py` | 修正 | 追加 API が必要なら export を更新する。 |
| `docs/api.md` | 修正 | profile-driven open の例を追加する。 |
| `tests/unit/test_profile_preset_open_capture.py` | 新規 | preset 解決と `open_capture(profile=...)` を fake opener で検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| profile config を作る | `CaptureConfig.for_profile("n3dsxl")` | N3DSXL default の config を返す | 実機 command なし |
| high-level open | `open_capture(profile="n3dsxl")` | N3DSXL reader を開く | 実機 command boundary は従来通り open 時 |
| output override | `output="both_vertical"` | config default を上書きする | profile supported outputs で validation |
| colorspace override | `colorspace="BGR"` | BGR read default になる | NyX / OpenCV 接続用 |
| backend preference | `backend="auto"` | resolver に従う | `local_028` と整合 |
| low-level tuning override | explicit `config=...` | 明示 config を尊重する | 通常 GUI では使わない |
| target FPS default | `target_fps=None` | native profile default | non-None の実効制御は `local_030` |
| unknown profile | `profile="classic_ds"` | profile registry の error を返す | source audit 前に暗黙追加しない |
| conflicting source/profile | `source="new_3ds_xl", profile="n3dsxl"` | 同義なら許可 | 矛盾する場合は error |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | `CaptureConfig.for_profile("n3dsxl")` は既存 default と互換である | compatibility | 3.1 | model / output / colorspace |
| todo | `open_capture(profile="n3dsxl", _opener=fake)` は fake opener に profile config を渡す | new behavior | 3.1 | 実機なし |
| todo | profile supported output 以外は validation error | edge | 3.1 | metadata と config を接続 |
| todo | `colorspace="BGR"` override が config に反映される | new behavior | 3.1 | NyX use case |
| todo | unknown profile は明示 error | edge | 3.1 | typo 検知 |
| todo | source/profile conflict は error | edge | 3.1 | 二重指定の曖昧さ回避 |
| todo | `profile` 引数追加後も既存 `open_capture()` 呼び出しは壊れない | regression | 3.1 | backward compatible |

### 3.3 設計方針

profile-driven API は既存 `open_capture()` の上位互換として追加する。既存の `source=0` と `source="new_3ds_xl"` は当面維持し、`profile="n3dsxl"` を推奨 path とする。

low-level tuning は `CaptureConfig` から消さない。hardware / performance 調整や開発用途では必要だが、通常利用者は `CaptureConfig.for_profile()` と high-level keyword で足りる形にする。

## 4. 実装仕様

```python
@dataclass(slots=True)
class CaptureConfig:
    source: CaptureSource = 0
    profile: str = "n3dsxl"
    model: Literal["new_3ds_xl"] = "new_3ds_xl"
    backend: CaptureBackend = "auto"
    mode_3d: bool = False
    output: CaptureOutput = CaptureOutput.BOTH_VERTICAL
    colorspace: ColorSpace = "RGB"
    target_fps: float | None = None
    raw_slots: int = 2
    output_queue_size: int = 2
    drop_policy: DropPolicy = "drop_oldest"
    poll_interval: float = 0.004
    read_timeout: float | None = 1.0
    collect_timing: bool = False

    @classmethod
    def for_profile(
        cls,
        profile: str,
        *,
        backend: CaptureBackend = "auto",
        output: CaptureOutput | str | None = None,
        colorspace: ColorSpace | None = None,
        target_fps: float | None = None,
    ) -> "CaptureConfig":
        ...
```

`open_capture()` は次の引数を受ける。

```python
def open_capture(
    source: CaptureSource = 0,
    *,
    profile: str | None = None,
    config: CaptureConfig | None = None,
    backend: CaptureBackend | None = None,
    output: CaptureOutput | str | None = None,
    colorspace: ColorSpace | None = None,
    target_fps: float | None = None,
    read_timeout: float | None = None,
    _opener: CaptureOpener | None = None,
) -> CaptureReader:
    ...
```

conflict rule:

| 入力 | 結果 |
| ---- | ---- |
| `profile=None`, `source=0` | 既存互換。`n3dsxl` として解決 |
| `profile="n3dsxl"`, `source=0` | 許可 |
| `profile="n3dsxl"`, `source="new_3ds_xl"` | 許可 |
| `profile="n3dsxl"`, `source=<device_id>` | `local_031` 実装後に許可を検討 |
| profile と source/model が矛盾 | `UnsupportedOperation` または structured config error |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| `for_profile` | default 解決 | `n3dsxl` | model / output / colorspace が仕様通り |
| `for_profile` | override | `colorspace="BGR"` | config に反映 |
| `open_capture` | profile keyword | fake opener | config.profile が `n3dsxl` |
| validation | unsupported output | fake profile | error |
| validation | unknown profile | `classic_ds` | error |
| regression | 既存呼び出し | `open_capture(_opener=fake)` | 従来通り reader |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| docs example | profile open の example | 実機なし fake | import と config 解決が成立 |
| hardware high-level | `open_capture(profile="n3dsxl")` | 実機、承認済み command | 既存 high-level E2E と同等に frame を読める |

### 検証コマンド

```console
uv run pytest tests/unit/test_profile_preset_open_capture.py
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

Hardware gate は実装後、人間承認を得てから実行する。

## 6. 実装チェックリスト

- [ ] `CaptureConfig` に `profile` と `target_fps` の field を追加する。
- [ ] `CaptureConfig.for_profile()` を実装する。
- [ ] `open_capture(profile=...)` を既存呼び出し互換で追加する。
- [ ] profile supported outputs と colorspace validation を接続する。
- [ ] docs/api に profile-driven open 例を追加する。
- [ ] unit test と static gate を実行する。
- [ ] 必要なら承認後に実機 high-level smoke を実行する。
