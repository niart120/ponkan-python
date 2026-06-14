# Capture Frame Pacing 仕様書

更新日: 2026-06-14

## 1. 概要

### 1.1 目的

`target_fps` を high-level capture API に追加し、profile native FPS より低い delivery FPS を ponkan-python 側で制御できるようにする。NyX などの利用側が `read()` 後に単純間引きするだけでは USB read / decode / queue の負荷を十分に制御できないため、reader / streaming layer の contract と diagnostics を定義する。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| target FPS | 利用者が希望する frame delivery rate。`None` は profile native default。 |
| native FPS | profile の実機 capture が自然に供給する FPS。N3DSXL は約 59.8fps。 |
| resolved target FPS | validation / clamp / fallback 後に実際に使う FPS。 |
| pacing drop | target FPS を守るために decode または delivery 前後で捨てた frame。 |
| delivery pacing | consumer に渡す frame 数を制御すること。 |
| acquisition throttling | backend read submit 自体の頻度を下げること。安全性と backend 制約の確認が必要。 |

### 1.3 背景・問題

現行 `CaptureReader` は backend completion と polling / queue policy に従い、N3DSXL ではほぼ native 約 60fps 前提で動く。NyX には camera / window source 向けの `capture_fps` があるが、ponkan-python で target FPS を指定する API はない。

利用側で `read()` 結果を間引くだけでは、USB read、decode、queue delivery の負荷は下がらない。初期実装では安全な delivery pacing と diagnostics を必須にし、backend ごとの acquisition throttling は測定と safety が取れた場合の拡張とする。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| FPS 指定 | public API なし | `open_capture(..., target_fps=30)` を指定できる |
| native 動作 | 約 60fps 前提 | `target_fps=None` で従来動作 |
| 低 FPS 利用 | 利用側で read 後に間引く | reader / streaming layer が pacing する |
| 過大 FPS | 暗黙動作 | validation error または clamp + warning を明示 |
| diagnostics | delivered / dropped はあるが pacing 理由がない | resolved FPS、effective FPS、pacing drop を stats で確認できる |

### 1.5 着手条件

- [ ] `local_029` で `CaptureConfig.target_fps` が追加済みである。
- [ ] `local_027` の profile metadata から native FPS を取得できる。
- [ ] existing `StreamStats` の counter 追加が既存 artifacts と互換になる方針を決める。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_030/CAPTURE_FRAME_PACING.md` | 新規 | target FPS / pacing / diagnostics の仕様を定義する。 |
| `src/ponkan/capture.py` | 修正 | `target_fps` validation と `CaptureReader` の pacing behavior を追加する。 |
| `src/ponkan/streaming/engine.py` | 修正 | pacing policy を streaming layer に接続する。 |
| `src/ponkan/streaming/stats.py` | 修正 | pacing diagnostics と resolved target FPS を追加する。 |
| `src/ponkan/profiles.py` | 修正 | native FPS metadata を pacing validation に提供する。 |
| `docs/api.md` | 修正 | `target_fps` の semantics と制約を追記する。 |
| `tests/unit/test_capture_frame_pacing.py` | 新規 | fake clock / fake frames で pacing を検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| native default | `target_fps=None` | 従来通り native に近い delivery | behavior regression を避ける |
| 60fps 指定 | `target_fps=60` | N3DSXL native に近い pacing | native よりわずかに高い場合の許容幅を定義 |
| 30fps 指定 | `target_fps=30` | delivery が約 30fps になる | frame drop / pacing を stats に記録 |
| 15fps 指定 | `target_fps=15` | delivery が約 15fps になる | read loop が過剰に busy wait しない |
| 0 以下 | `target_fps <= 0` | validation error | config error |
| native より高い | `target_fps > native_fps` | validation error、または resolved target + warning | 実装時にどちらかを固定 |
| diagnostics | stats 取得 | effective FPS、pacing drop、resolved target を確認できる | JSON serializable |
| shutdown | pacing 有効中に close | pending transfer cancel / drain / release を維持 | safety |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | `target_fps=None` は pacing なしで既存 read behavior | regression | 3.1 | fake engine |
| todo | `target_fps=30` は fake clock 上で delivery interval を守る | new behavior | 3.1 | deterministic clock |
| todo | pacing drop が stats に加算される | diagnostics | 3.1 | `paced_dropped` など |
| todo | `target_fps <= 0` は validation error | edge | 3.1 | config validation |
| todo | native より高い FPS は仕様通り error / clamp になる | edge | 3.1 | policy 固定 |
| todo | close 時の cleanup は pacing 有無で変わらない | cleanup | 3.1 | fake engine stop count |

### 3.3 設計方針

初期実装は delivery pacing を必須範囲にする。backend acquisition throttling は、USB command sequence や in-flight transfer safety への影響があるため、N3DSXL 実機で測定してから別の最適化として扱う。

ただし、利用側で read 後に間引くよりは ponkan-python 内部で制御する。`CaptureReader.read()` が不要に古い frame を返さず、streaming queue と stats に pacing reason が残ることを優先する。

## 4. 実装仕様

`CaptureConfig` に追加済みの `target_fps` を validation する。

```python
def validate_target_fps(target_fps: float | None, *, native_fps: float | None) -> float | None:
    if target_fps is None:
        return None
    if target_fps <= 0:
        raise ValueError("target_fps must be positive or None")
    if native_fps is not None and target_fps > native_fps * 1.01:
        raise ValueError("target_fps must not exceed profile native_fps")
    return target_fps
```

stats 追加案:

```python
@dataclass(slots=True)
class StreamStats:
    submitted: int = 0
    completed: int = 0
    decoded: int = 0
    delivered: int = 0
    dropped_raw: int = 0
    dropped_decoded: int = 0
    dropped_pacing: int = 0
    resolved_target_fps: float | None = None
    effective_delivered_fps: float | None = None
```

pacing policy:

| Phase | 必須 | 内容 |
| ----- | ---- | ---- |
| Phase 1 | 必須 | decoded / queued frame から delivery interval に合う最新 frame だけ返す |
| Phase 2 | 任意 follow-up | safe な backend で decode scheduling や acquisition submit を減らす |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| validation | positive FPS | `30` | accepted |
| validation | invalid FPS | `0`, `-1` | error |
| validation | over native | `120` on N3DSXL | error / clamp policy 通り |
| read pacing | 30fps interval | fake clock | delivery interval が概ね 33ms |
| stats | pacing drop | extra frames | counter が増える |
| cleanup | close | pacing enabled | stop は 1 回 |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| 30fps smoke | target FPS 30 の read loop | 実機、承認済み command | effective FPS が目標範囲、usb/decode error なし |
| native regression | target FPS None | 実機、承認済み command | 既存 performance gate と同等 |

### 検証コマンド

```console
uv run pytest tests/unit/test_capture_frame_pacing.py
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

Hardware gate は承認後に `requires_n3dsxl` / `performance` marker 付きで実行する。

## 6. 実装チェックリスト

- [ ] `target_fps` validation policy を固定する。
- [ ] delivery pacing を fake clock で deterministic に test する。
- [ ] pacing diagnostics を `StreamStats` / performance artifact に追加する。
- [ ] `docs/api.md` に `target_fps` の制約を追記する。
- [ ] local gate を実行する。
- [ ] 承認後に N3DSXL 30fps smoke と native regression を実行する。
