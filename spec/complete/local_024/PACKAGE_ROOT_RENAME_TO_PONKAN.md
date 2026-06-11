# パッケージルートを `ponkan` に変更する仕様書

## 1. 概要

### 1.1 目的

Python import package root を `py3dscapture` から `ponkan` に変更する。
distribution name は `ponkan-python` のまま維持し、利用者向け import 例、console script、開発設定、Codex hook、テスト、現行ドキュメントの参照名を `ponkan` に揃える。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| distribution name | PyPI / packaging 上の配布名。現行どおり `ponkan-python`。 |
| import package root | Python import で使う top-level package 名。本仕様で `py3dscapture` から `ponkan` に変更する。 |
| console script | `pyproject.toml` の `[project.scripts]` で公開する CLI command。 |
| compatibility shim | 旧 `py3dscapture` import を新 `ponkan` に転送する互換 package。 |
| canonical docs | README、API reference、publishing notes、AGENTS、初期仕様など、今後の作業で参照する文書。 |
| historical specs | `spec/complete/local_*` の完了済み Work Unit 仕様。完了時点の証跡を含む。 |

### 1.3 背景・問題

現状は配布名が `ponkan-python` である一方、import package root と CLI prefix は `py3dscapture` である。
この不一致により、README/API の利用例、publishing smoke check、agent 向け構造説明、実装上の first-party package 設定が分散している。

事実:

- `rg --files-with-matches "py3dscapture"` で 84 files が一致した。
- `rg --stats "py3dscapture"` で 417 matches / 403 matched lines が一致した。
- `src/py3dscapture` 配下には 33 files がある。
- `pyproject.toml` は script entry point、wheel package、Ruff per-file ignore、isort first-party 設定で `py3dscapture` を参照している。
- `.codex/hooks/pre_tool_use_policy.py` は実機 command の検出 regex で `py3dscapture.tools.capture_raw` と `py3dscapture.tools.stream_n3dsxl` を参照している。

仮説:

- pre-alpha 段階の breaking rename として扱えば、互換 shim を残すより実装・検証面が単純になる。
- 旧名 compatibility shim が必要な場合は、本仕様とは別 Work Unit で移行期間と deprecation policy を決める方がよい。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| import root | `py3dscapture` | `ponkan` |
| distribution name | `ponkan-python` | `ponkan-python` のまま |
| public import example | `from py3dscapture import ...` | `from ponkan import ...` |
| source package path | `src/py3dscapture` | `src/ponkan` |
| first-party lint 設定 | `known-first-party = ["py3dscapture"]` | `known-first-party = ["ponkan"]` |
| console script prefix | `py3dscapture-*` | `ponkan-*` |
| canonical docs の旧名参照 | README/API/publishing/AGENTS/spec initial に残存 | 現行仕様として必要な箇所は `ponkan` に更新 |

### 1.5 着手条件

- [x] `master` が clean であることを確認した。
- [x] 作業ブランチ `docs/package-root-ponkan` を作成した。
- [x] `spec-format` の配置規約に従い `spec/wip/local_024/` を採番し、完了後に `spec/complete/local_024/` へ移動した。
- [x] `py3dscapture` 参照の repo-wide grep を実施した。
- [x] 実装時に互換 shim を入れない breaking rename として進めることを再確認した。

## 2. 対象ファイル

### 2.1 修正対象

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `src/py3dscapture/**` | 移動 / 修正 | `src/ponkan/**` へ移動し、package 内 import を `ponkan.*` に変更する。`py.typed` も新 package root に移す。 |
| `pyproject.toml` | 修正 | `[project.scripts]` の command 名と module path、Hatch wheel package、Ruff per-file ignore、isort first-party package を `ponkan` に更新する。 |
| `tests/unit/**/*.py` | 修正 | import、module path assertion、script entry point expectation、source path assertion を `ponkan` に更新する。 |
| `tests/e2e/**/*.py` | 修正 | 実機 gated test の import を `ponkan` に更新する。実機 command 自体はこの仕様書作成時点では実行しない。 |
| `tests/performance/**/*.py` | 修正 | performance smoke test の import を `ponkan` に更新する。 |
| `tests/manual/**/*.py` | 修正 | manual visual helper の import と module path を `ponkan` に更新する。 |
| `tests/conftest.py` | 修正 | hardware gate import を `ponkan` に更新する。 |
| `.codex/hooks/pre_tool_use_policy.py` | 修正 | 実機 command block regex を `uv run python -m ponkan.tools.capture_raw` と `uv run python -m ponkan.tools.stream_n3dsxl` に対応させる。 |
| `README.md` | 修正 | import example と CLI command example を `ponkan` / `ponkan-*` に更新する。 |
| `docs/api.md` | 修正 | API reference の package 名、import example、CLI table を `ponkan` / `ponkan-*` に更新する。 |
| `docs/publishing.md` | 修正 | import package 名と post-publish smoke check を `ponkan` / `ponkan-*` に更新する。 |
| `AGENTS.md` | 修正 | project structure の package root を `src/ponkan/` に更新する。 |
| `spec/initial/cc3dsfs_python_rebuild_spec.md` | 修正 | 初期構想の package layout と public import examples を `ponkan` に更新し、旧名からの変更履歴を短く記録する。 |
| `spec/initial/cc3dsfs_python_n3dsxl_implementation_workflow.md` | 修正 | workflow command example を `uv run python -m ponkan.tools.*` に更新する。 |

### 2.2 調査対象だが原則として直接修正しないファイル

| ファイル | 扱い | 理由 |
| -------- | ---- | ---- |
| `spec/complete/local_*/**/*.md` | 原則未修正 | 完了済み Work Unit の時点証跡を保持するため。必要なら本仕様からの追跡参照で補う。 |
| `LICENSE` / `NOTICE.md` | 対象外 | package root rename と著作権表示は独立している。 |
| `.github/workflows/**` | 現時点で一致なし | `py3dscapture` 参照が検出されていないため。実装時に再 grep する。 |

### 2.3 代表的な現行一致箇所

| 領域 | 代表例 | 変更後 |
| ---- | ------ | ------ |
| source path | `src/py3dscapture/capture.py` | `src/ponkan/capture.py` |
| package import | `from py3dscapture import open_capture` | `from ponkan import open_capture` |
| submodule import | `from py3dscapture.protocol.sizes import capture_size` | `from ponkan.protocol.sizes import capture_size` |
| module command | `uv run python -m py3dscapture.tools.stream_n3dsxl` | `uv run python -m ponkan.tools.stream_n3dsxl` |
| console script | `py3dscapture-stream-n3dsxl` | `ponkan-stream-n3dsxl` |
| wheel package | `packages = ["src/py3dscapture"]` | `packages = ["src/ponkan"]` |
| first-party package | `known-first-party = ["py3dscapture"]` | `known-first-party = ["ponkan"]` |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| top-level package import | editable install または `uv run` 環境で `import ponkan` | 例外なく import でき、既存 public API を expose する | `__all__` の意味は維持する。 |
| high-level API import | `from ponkan import CaptureOutput, open_capture` | 現行 `py3dscapture` と同等の object を import できる | API 名は変えない。 |
| submodule import | `from ponkan.protocol.sizes import capture_size` | 現行と同じ関数を import できる | package root だけを変更する。 |
| old package import | `import py3dscapture` | 互換 shim を採用しない場合は成功を保証しない | breaking rename。shim が必要なら別仕様で扱う。 |
| console script | `ponkan-list-devices --help` など | 新 command 名で CLI が起動する | 実機 command 送信の有無は既存 CLI の安全境界に従う。 |
| module command | `uv run python -m ponkan.tools.capture_raw ...` | 既存 CLI module と同じ処理に入る | 実機 command は承認なしで実行しない。 |
| Codex hardware policy | 承認なしの `uv run python -m ponkan.tools.capture_raw` | hook が block する | 旧名だけ block して新名を通す regression を避ける。 |
| packaging | `uv build` | wheel に `ponkan` package と `py.typed` が含まれる | distribution name は `ponkan-python`。 |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | `tests/unit/test_package.py` を `import ponkan` と `ponkan-*` script expectation に更新する | regression | 3.1 | 先に red を確認し、package rename 後に green。 |
| green | `uv run pytest tests/unit/test_package.py` が通る | regression | 3.1 | package metadata と public import の最小 gate。 |
| green | source / tests の import を `ponkan.*` に更新し、unit tests が通る | regression | 3.1 | 実機不要。 |
| green | `.codex/hooks/pre_tool_use_policy.py` が `ponkan.tools.capture_raw` / `ponkan.tools.stream_n3dsxl` を hardware command として検出する | safety regression | 3.1 | `tests/unit/test_codex_pre_tool_use_policy.py` を追加。 |
| green | `rg -n "py3dscapture" src tests README.md docs AGENTS.md pyproject.toml .codex spec/initial` が一致なしになる | documentation / hygiene | 2.1 | `spec/complete` は対象外。 |
| green | `uv run ruff format --check .` が通る | quality gate | 5 | path rename 後の import ordering を確認済み。 |
| green | `uv run ruff check .` が通る | quality gate | 5 | first-party 設定更新を含む。 |
| green | `uv run ty check --no-progress` が通る | quality gate | 5 | package root rename の型解決を確認済み。 |
| green | `uv run pytest tests/unit` が通る | regression | 5 | 実機不要の範囲。 |
| green | `uv build` が通る | packaging | 3.1 | wheel/sdist の package include を確認済み。 |

### 3.3 設計方針

- distribution name `ponkan-python` は変更しない。
- import package root は `ponkan` に一本化する。
- compatibility shim はこの Work Unit では作らない。理由は、旧 root を残すと `rg` gate、public surface、doc example、typing package data の判断が増えるため。
- CLI command は package root と揃えて `ponkan-*` に変更する。旧 `py3dscapture-*` script alias は作らない。
- 実機動作、USB command sequence、backend selection、streaming behavior は変更しない。
- `spec/complete` は履歴として保持する。新仕様以降の正本はこの `local_024` と更新後の canonical docs とする。
- path rename は `git mv src/py3dscapture src/ponkan` を使い、履歴追跡を保つ。

## 4. 実装仕様

### 4.1 Public import surface

```python
from ponkan import (
    ACCEPTED_N3DSXL_PRODUCT_IDS,
    ACCEPTED_N3DSXL_PRODUCT_STRINGS,
    N3DSXL_VENDOR_ID,
    CaptureConfig,
    CaptureOutput,
    CaptureReader,
    CaptureSizes,
    capture_sizes,
    open_capture,
)
```

### 4.2 Module command surface

```console
uv run python -m ponkan.tools.list_devices
uv run python -m ponkan.tools.capture_raw --model new_3ds_xl --out captures/n3dsxl/raw_2d_001.bin
uv run python -m ponkan.tools.raw_to_png captures/n3dsxl/raw_2d_001.bin --metadata captures/n3dsxl/raw_2d_001.json --out captures/n3dsxl/png
uv run python -m ponkan.tools.stream_n3dsxl --duration 10 --stats
```

### 4.3 Console script surface

```console
ponkan-list-devices
ponkan-capture-raw --out captures/n3dsxl/raw_2d_001.bin
ponkan-raw-to-png captures/n3dsxl/raw_2d_001.bin --metadata captures/n3dsxl/raw_2d_001.json --out captures/n3dsxl/png
ponkan-stream-n3dsxl --duration 10 --stats
```

### 4.4 Packaging configuration

`pyproject.toml` の期待形:

```toml
[project.scripts]
ponkan-capture-raw = "ponkan.tools.capture_raw:main"
ponkan-list-devices = "ponkan.tools.list_devices:main"
ponkan-raw-to-png = "ponkan.tools.raw_to_png:main"
ponkan-stream-n3dsxl = "ponkan.tools.stream_n3dsxl:main"

[tool.hatch.build.targets.wheel]
packages = ["src/ponkan"]

[tool.ruff.lint.per-file-ignores]
"src/ponkan/tools/**/*.py" = ["T201"]

[tool.ruff.lint.isort]
known-first-party = ["ponkan"]
```

### 4.5 Codex hook safety

`.codex/hooks/pre_tool_use_policy.py` の hardware command pattern は、少なくとも次を検出する。

```text
uv run python -m ponkan.tools.capture_raw
uv run python -m ponkan.tools.stream_n3dsxl
```

必要に応じて旧 `py3dscapture.tools.*` も block 対象として残すことは許容する。
ただし、実装完了後の public docs では旧 command を案内しない。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| package import | top-level public API が import できる | `import ponkan` | 例外なし、既存 `__all__` contract 維持 |
| project scripts | script 名と module path が新名になっている | `tests/unit/test_package.py` | `ponkan-*` と `ponkan.tools.*` を期待 |
| source imports | package 内 absolute import が新名に揃う | `uv run pytest tests/unit` | unit tests pass |
| hook policy | 新 module command を実機 command として検出する | `uv run python -m ponkan.tools.capture_raw` | 承認なしでは violation |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| docs grep | canonical docs と source/test/config の旧名残存を確認 | 実装完了後 | `rg -n "py3dscapture" src tests README.md docs AGENTS.md pyproject.toml .codex spec/initial` が一致なし |
| build | wheel/sdist の package include を確認 | dev dependencies synced | `uv build` が通る |
| e2e import collection | 実機 gated tests が import collection で壊れない | 実機 env flag なし | `uv run pytest --collect-only tests/e2e tests/performance` が import error なし |

### 検証コマンド

```console
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
uv run pytest --collect-only tests/e2e tests/performance
rg -n "py3dscapture" src tests README.md docs AGENTS.md pyproject.toml .codex spec/initial
uv build
```

実機 command はこの rename の必須 gate ではない。
既存の実機 E2E / performance を実行する場合は、device identity、command scope、安全理由、artifact、cleanup を提示し、人間の明示承認後に `PONKAN_HARDWARE_APPROVED=1` を同じ command 内で指定する。

## 6. 実装チェックリスト

- [x] `tests/unit/test_package.py` を `ponkan` package root と `ponkan-*` console script expectation に更新して red を確認する。
- [x] `git mv src/py3dscapture src/ponkan` で source package を移動する。
- [x] `src/ponkan/**/*.py` の absolute import と内部文字列で package root を表す箇所を `ponkan` に更新する。
- [x] `pyproject.toml` の scripts、wheel package、Ruff per-file ignore、isort first-party 設定を更新する。
- [x] `tests/**/*.py` の import、path assertion、module path expectation を更新する。
- [x] `.codex/hooks/pre_tool_use_policy.py` と hook policy test を更新する。
- [x] `README.md`、`docs/api.md`、`docs/publishing.md`、`AGENTS.md` を更新する。
- [x] `spec/initial/cc3dsfs_python_rebuild_spec.md` と `spec/initial/cc3dsfs_python_n3dsxl_implementation_workflow.md` を更新する。
- [x] `rg -n "py3dscapture" src tests README.md docs AGENTS.md pyproject.toml .codex spec/initial` が一致しないことを確認する。
- [x] `uv run ruff format --check .` を実行する。
- [x] `uv run ruff check .` を実行する。
- [x] `uv run ty check --no-progress` を実行する。
- [x] `uv run pytest tests/unit` を実行する。
- [x] `uv run pytest --collect-only tests/e2e tests/performance` を実行する。
- [x] `uv build` を実行する。
- [x] gate 結果と未実行 gate を仕様書または PR description に反映する。

## 7. Gate 結果

| Gate | 結果 | 証跡 |
| ---- | ---- | ---- |
| red 確認 | fail as expected | `uv run pytest tests/unit/test_package.py` が `ModuleNotFoundError: No module named 'ponkan'` で collection error。 |
| package / hook targeted | pass | `uv run pytest tests/unit/test_codex_pre_tool_use_policy.py tests/unit/test_package.py` -> 5 passed。 |
| format | pass | `uv run ruff format --check .` -> 70 files already formatted。 |
| lint | pass | `uv run ruff check .` -> All checks passed。 |
| type check | pass | `uv run ty check --no-progress` -> All checks passed。 |
| unit tests | pass | `uv run pytest tests/unit` -> 124 passed。 |
| e2e / performance collection | pass | `uv run pytest --collect-only tests/e2e tests/performance` -> 14 tests collected。 |
| canonical 旧名 grep | pass | `rg -n "py3dscapture" src tests README.md docs AGENTS.md pyproject.toml .codex spec/initial` -> 一致なし。 |
| old source package absence | pass | `Test-Path src\py3dscapture` -> `False`。 |
| runtime import / no shim | pass | `uv run python -c "import importlib.util; import ponkan; print(ponkan.__name__); print(importlib.util.find_spec('py3dscapture'))"` -> `ponkan` / `None`。 |
| build | pass | `uv build` -> `dist\ponkan_python-0.1.0.tar.gz` と `dist\ponkan_python-0.1.0-py3-none-any.whl` を生成。 |

実機 E2E / performance 実行はこの rename の必須 gate ではないため未実行。
