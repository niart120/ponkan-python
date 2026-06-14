# Profile Preset Open Capture 仕様書

更新日: 2026-06-14

## 1. 概要

### 1.1 目的

この仕様は白紙化する。`CaptureConfig.for_profile()`、`open_capture(profile=...)`、profile preset 解決は現時点の実装対象にしない。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| deferred | 現時点では実装しない。後続の利用実績や API 不足が明確になった場合に、別仕様として再設計する状態。 |
| profile preset | `CaptureProfile` から `CaptureConfig` を生成する構想。現時点では採用しない。 |

### 1.3 背景・問題

レビューで、この仕様は `CaptureConfig.for_profile()`、`open_capture(profile=...)`、`target_fps`、`source/profile` conflict rule まで同時に追加し、既存の薄い `open_capture()` / `CaptureReader.read()` API を太らせるリスクが高いと判断した。

`local_027` の profile registry と `local_028` の backend capability API だけで、利用側は当面 `open_capture()` の既存 contract と `CaptureOutput` を使える。profile preset は、実際に複数 profile が実装され、既存 `CaptureConfig` では重複や曖昧さが避けられないことが分かってから再検討する。

### 1.4 期待効果

| 指標 | 白紙化前 | 白紙化後 |
| ---- | -------- | -------- |
| API surface | `CaptureConfig.for_profile()` と `open_capture(profile=...)` を追加する計画 | 既存 `open_capture()` を維持する |
| 実装範囲 | profile preset、target FPS、conflict rule が混在 | `local_027` / `local_028` の薄い metadata contract に集中する |
| 再検討条件 | 未定義 | 複数 profile 実装後、preset なしでは利用側の重複が大きいと確認できた時点 |

### 1.5 着手条件

- [ ] 複数 capture profile が実装済みである。
- [ ] 既存 `CaptureConfig` と `open_capture()` では利用側の重複や曖昧さが実害になっている。
- [ ] `profile` keyword を追加しても既存 `source` / `model` contract を複雑にしない設計がある。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_029/PROFILE_PRESET_OPEN_CAPTURE.md` | 白紙化 | 過剰仕様として deferred にする。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| 既存 open API を使う | `open_capture()` | 従来通り N3DSXL reader を開く | 新しい `profile` keyword は追加しない |
| profile metadata を参照する | `get_capture_profile("n3dsxl")` | default output や support status を確認できる | `local_027` の責務 |
| backend capability を確認する | `resolve_backend(...)` | backend の診断ができる | `local_028` の責務 |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| deferred | `CaptureConfig.for_profile()` を追加する | API design | 3.1 | 現時点では実装しない |
| deferred | `open_capture(profile=...)` を追加する | API design | 3.1 | 現時点では実装しない |

### 3.3 設計方針

profile-driven open は、profile registry と backend capability の利用実績を見てから再設計する。現時点では「profile metadata を取得できる」ことと「既存 `open_capture()` が薄く保たれる」ことを優先する。

## 4. 実装仕様

実装なし。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| なし | なし | なし | なし |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| なし | なし | なし | なし |

### 検証コマンド

```console
git diff --check
```

## 6. 実装チェックリスト

- [x] 過剰仕様として白紙化する。
- [x] 後続実装候補から外す。
