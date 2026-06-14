# Capture Frame Pacing 仕様書

更新日: 2026-06-14

## 1. 概要

### 1.1 目的

この仕様は白紙化する。`target_fps`、reader 内 pacing、`StreamStats` の pacing diagnostics は現時点の実装対象にしない。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| deferred | 現時点では実装しない。実測と具体的な利用側要求が揃った場合に、別仕様として再設計する状態。 |
| caller-side sampling | 利用側が `CaptureReader.read()` を任意間隔で呼び、必要な最新 frame だけを取得する使い方。 |

### 1.3 背景・問題

レビューで、この仕様の必須範囲は delivery pacing に留まり、USB read / decode / queue 負荷を根本的に下げる acquisition throttling までは扱えていないと判断した。利用側が最新 frame を任意間隔で取得する使い方で十分なら、ponkan-python 側に `target_fps` public API を追加する必要は薄い。

N3DSXL streaming の performance や latency を変える作業は、既存 `local_021` の測定方針と同じく、実測を起点にした個別 optimization として扱う。

### 1.4 期待効果

| 指標 | 白紙化前 | 白紙化後 |
| ---- | -------- | -------- |
| API surface | `target_fps` を high-level API に追加する計画 | 既存 `read()` 呼び出し間隔で利用側が調整する |
| 負荷軽減 | delivery pacing だけでは USB/decode 負荷は下がりにくい | 誤った期待を public API に固定しない |
| 再検討条件 | 未定義 | caller-side sampling では不足する実測 evidence が出た時点 |

### 1.5 着手条件

- [ ] caller-side sampling では負荷、latency、jitter、または UX 要件を満たせない実測 evidence がある。
- [ ] acquisition throttling が N3DSXL command sequence、pending transfer、shutdown safety を壊さない設計がある。
- [ ] performance / hardware gate の acceptance を先に定義できる。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_030/CAPTURE_FRAME_PACING.md` | 白紙化 | `target_fps` / pacing 仕様を deferred にする。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| latest frame を取得する | 利用側が任意間隔で `read()` を呼ぶ | 既存 reader semantics に従って最新 frame を取得する | 新しい `target_fps` は追加しない |
| native streaming を維持する | `target_fps` 指定なし | 従来の N3DSXL streaming behavior を維持する | regression を避ける |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| deferred | `target_fps` を追加する | API design | 3.1 | 現時点では実装しない |
| deferred | delivery pacing stats を追加する | diagnostics | 3.1 | 現時点では実装しない |
| deferred | acquisition throttling を実装する | performance | 3.1 | 実測 evidence が必要 |

### 3.3 設計方針

利用側が必要な頻度で `read()` を呼ぶ設計を優先する。ponkan-python 側で FPS API を持つ場合は、delivery-only ではなく、取得負荷を実際に下げる設計と実機 gate を伴う別 Work Unit として再設計する。

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

- [x] `target_fps` / pacing 仕様を白紙化する。
- [x] 後続実装候補から外す。
