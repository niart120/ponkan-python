# AI Agent・開発環境初期整備 仕様書

## 1. 概要

### 1.1 目的

`ponkan-python` を、`cc3dsfs` を参照した new 3DS XL 映像取得向け Python ライブラリとして開発できる状態に整える。実装着手前の AI Agent ガードレール、開発依存、テストハーネス、GitHub 公開準備を初期基準として固定する。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| ponkan-python | このリポジトリの distribution 名。 |
| py3dscapture | Python import package 名。 |
| cc3dsfs | 参照元の C++ 実装。`Lorenzooone/cc3dsfs` を指す。 |
| N3DSXL | new 3DS XL capture board。MVP の実機対象。 |
| 実機テスト | USB device に command を送るテスト。CI では実行しない。 |
| Agent skill | `.agents/skills` 配下で管理する AI Agent 向け作業手順。 |

### 1.3 背景・問題

現状の `AGENTS.md` は別プロジェクト NyX 向けであり、USB device command の安全制約や `cc3dsfs` 参照作業の記録ルールがない。`pyproject.toml` は package 名・依存・テスト設定が未整備で、`README.md`、LICENSE、GitHub template、CI、pytest marker も公開準備に足りない。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| Agent 指示の適合度 | NyX 向けで不一致 | ponkan-python / N3DSXL 向けに一致 |
| 開発環境復元性 | `pyproject.toml` が最小状態 | `uv` で dev/test 環境を復元可能 |
| CI 実行範囲 | 未整備 | 実機不要の静的・単体チェックのみ実行 |
| 実機安全制約 | 明文化なし | 未知 device への command 禁止を明文化 |

### 1.5 着手条件

- [x] `spec/initial/cc3dsfs_python_rebuild_spec.md` が存在する
- [x] `spec/initial/cc3dsfs_python_n3dsxl_implementation_workflow.md` が存在する
- [x] distribution 名は `ponkan-python` を維持する
- [x] import package 名は `py3dscapture` とする
- [x] LICENSE は MIT とする

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/complete/local_001/AGENT_ENVIRONMENT_BOOTSTRAP.md` | 新規 | 本作業仕様書を完了状態で保存する |
| `AGENTS.md` | 修正 | ponkan-python 用の Agent ガードレールへ置換する |
| `pyproject.toml` | 修正 | package、依存、dev 依存、pytest/ruff/ty 設定を追加する |
| `README.md` | 修正 | プロジェクト説明、原典参照、開発コマンドを追加する |
| `LICENSE` | 新規 | MIT License を追加する |
| `src/ponkan_python/*` | 削除 | 初期 placeholder package を削除する |
| `src/py3dscapture/*` | 新規 | import package skeleton を追加する |
| `tests/*` | 新規 | unit/e2e/performance の pytest harness を追加する |
| `.github/workflows/ci.yml` | 新規 | 実機不要の CI を追加する |
| `.github/PULL_REQUEST_TEMPLATE.md` | 修正 | spec・原典参照・実機安全 checklist を追加する |
| `.github/ISSUE_TEMPLATE/*.md` | 修正/新規 | bug/hardware/feature 用 template に整理する |
| `.agents/skills/*` | 修正/新規 | ponkan-python 用 skill に更新する |
| `.gitignore` | 修正 | Python/test/artifact/cache の除外を追加する |
| `uv.lock` | 新規 | 初期 dev/runtime 依存の lock を追加する |

## 3. 設計方針

開発基盤は、実機なしで検証可能な静的チェックと単体テストを先に固定する。実機を必要とする処理は pytest marker と Agent ガードレールで分離し、CI から除外する。

外向きの説明では、`ponkan-python` は `cc3dsfs` の完全互換移植ではなく、参照実装に敬意を払いながら N3DSXL 映像取得に絞って Python で再構成する個人用途寄りのライブラリとして記述する。非互換範囲の長い列挙は避け、機能範囲を簡潔に示す。

package 構成は `src/py3dscapture` を採用し、distribution 名 `ponkan-python` とは分ける。初期 skeleton では USB command 実装に踏み込まず、定数・サイズ計算・公開 import の最小基盤だけ置く。

## 4. 実装仕様

`pyproject.toml` は `uv` 前提で、runtime と optional/dev dependencies を分離する。

```toml
[project]
name = "ponkan-python"
requires-python = ">=3.12, <3.14"
dependencies = [
    "libusb1",
    "numpy",
]

[project.optional-dependencies]
image = ["pillow"]
opencv = ["opencv-python"]

[dependency-groups]
dev = ["pytest", "pytest-cov", "ruff", "ty"]
```

pytest marker は実機系を明示的に分離する。

```python
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip hardware and performance tests unless explicit env vars are set."""
```

`AGENTS.md` には以下の禁止事項を含める。

```text
- product string が N3DSXL / N3DSXL.2 でない device に N3DSXL command を送らない
- 実機テストは `requires_n3dsxl` marker を付ける
- CI では実機テストを実行しない
- `cc3dsfs` 由来の command 値・構造体サイズ・USB sequence は参照元を記録する
```

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| package import | `py3dscapture` を import できる | `import py3dscapture` | 例外なし |
| N3DSXL constants | VID/PID/product string/endpoint が仕様値と一致する | 定数参照 | 仕様書の値と一致 |
| size calculation | 2D/3D video/capture size を算出できる | mode_3d false/true | 仕様書の初期計算値と一致 |
| pytest marker | 実機 marker が登録される | `pytest tests/unit` | unknown marker warning なし |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| CI static checks | ruff/ty/pytest unit を実行する | 実機なし | CI が成功する |
| 実機 test separation | `requires_n3dsxl` を CI 対象外にする | 実機なし | CI で実機テストを実行しない |

## 6. 実装チェックリスト

- [x] 作業仕様書を作成する
- [x] `AGENTS.md` を ponkan-python 用に更新する
- [x] `pyproject.toml` と package skeleton を整備する
- [x] README / LICENSE / GitHub template を整備する
- [x] Agent skills を ponkan-python 用に更新する
- [x] pytest harness と CI を追加する
- [x] `uv run ruff format --check .` を実行する
- [x] `uv run ruff check .` を実行する
- [x] `uv run ty check src/py3dscapture --output-format concise --no-progress` を実行する
- [x] `uv run pytest tests/unit` を実行する
- [x] 仕様書チェックリストを完了状態へ更新する

検証結果:

```text
uv run ruff format --check . -> 6 files already formatted
uv run ruff check . -> All checks passed
uv run ty check src/py3dscapture --output-format concise --no-progress -> All checks passed
uv run pytest tests/unit -> 5 passed
```
