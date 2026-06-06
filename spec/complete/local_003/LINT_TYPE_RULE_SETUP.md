# Ruff・ty ルール強化 仕様書

## 1. 概要

### 1.1 目的

`ponkan-python` の Python 実装品質を、実装初期から機械的に検査できる状態にする。docstring は Google style を基準にし、対立する docstring rule は無効化する。あわせて、バグ検出、型安全性、テスト品質、例外処理、import 整理に効く Ruff / ty 設定を強化する。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| Ruff | format と lint を担当する Python 静的解析 tool。 |
| ty | 型チェックを担当する Astral 製 Python type checker。 |
| docstring 系 rule | Ruff の `D` / `DOC` など、docstring の文体・形式を検査する rule。 |
| Google style | Google Python Style Guide の docstring convention。Ruff では `lint.pydocstyle.convention = "google"` で指定する。 |
| characterization test | 原典 `cc3dsfs` 由来の定数・サイズ・protocol 値を固定するためのテスト。 |

### 1.3 背景・問題

初期状態の Ruff 設定は `B`, `E`, `F`, `I`, `RUF`, `SIM`, `UP` のみで、型注釈漏れ、docstring style、pytest style、例外処理、pathlib 推奨、NumPy 固有問題、直接 `print`、security 系の検査が不足していた。ty は command line で `src/py3dscapture` のみを対象にしており、`tests` の型チェックや warning fatal 化が固定されていなかった。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| Ruff 検査範囲 | 最小 rule set | 実害検出に寄せた広い rule set |
| docstring 運用 | 未定 | Google style を採用し、対立 rule は無効化 |
| ty 対象範囲 | `src/py3dscapture` のみ | `src` と `tests` を対象にする |
| ty warning | command 依存 | warning を error として扱う |

### 1.5 着手条件

- [x] `pyproject.toml` に Ruff 設定が存在する
- [x] `pyproject.toml` に ty 設定を追加できる
- [x] Python package は `src/py3dscapture` に配置されている
- [x] unit test は `tests/unit` に配置されている

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `pyproject.toml` | 修正 | Ruff rule set、per-file ignore、type-checking strict、isort first-party、ty 設定を追加する |
| `uv.lock` | 修正 | Ruff / ty の下限 version 更新を反映する |
| `.gitattributes` | 新規 | 改行コードを LF 基準に固定する |
| `src/py3dscapture/protocol/sizes.py` | 修正 | Google style docstring rule に合わせて関数 docstring 直後の空行を削除する |
| `.codex/hooks/pre_tool_use_policy.py` | 修正 | public function に Google style docstring を追加する |
| `AGENTS.md` | 修正 | `ty check` を pyproject 設定利用の command に更新する |
| `README.md` | 修正 | `ty check` を pyproject 設定利用の command に更新する |
| `.github/PULL_REQUEST_TEMPLATE.md` | 修正 | 検証 command を更新する |
| `.github/workflows/ci.yml` | 修正 | CI の ty command を更新する |

## 3. 設計方針

Ruff は docstring 系 rule として `D` を採用し、Google style を基準にする。`D203` と `D213` は class docstring 前の空行や multi-line summary 位置で Google convention / Ruff formatter と対立するため無効化する。

採用 rule は、実害のあるバグ・保守性低下・テスト品質低下を検出するものに寄せる。Pylint 系は `PLC`, `PLE`, `PLW` に限定し、`PLR` は採用しない。`PLR2004` は characterization test の literal 値検証と衝突しやすいため、初期設定では除外する。

ty は `pyproject.toml` に設定を寄せ、command 側の path / output-format 指定を減らす。`src` と `tests` を対象にし、warning も失敗扱いにする。

## 4. 実装仕様

Ruff の採用カテゴリ:

```toml
[tool.ruff.lint]
select = [
    "A",
    "ANN",
    "ARG",
    "ASYNC",
    "B",
    "BLE",
    "C4",
    "D",
    "DTZ",
    "E",
    "F",
    "FURB",
    "I",
    "N",
    "NPY",
    "PERF",
    "PIE",
    "PLC",
    "PLE",
    "PLW",
    "PT",
    "PTH",
    "RET",
    "RUF",
    "S",
    "SIM",
    "SLOT",
    "T20",
    "TC",
    "TRY",
    "UP",
    "W",
]
```

per-file ignore:

```toml
[tool.ruff.lint.per-file-ignores]
"src/py3dscapture/tools/**/*.py" = ["T201"]
"tests/**/*.py" = ["D100", "D103", "S101"]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

`D203` / `D213` は Google convention では無効化される。`tests` はテスト名が仕様を担うため、module / function docstring 要求 (`D100`, `D103`) を外す。

ty 設定:

```toml
[tool.ty.environment]
python-version = "3.12"
root = ["./src"]

[tool.ty.src]
include = ["src", "tests"]

[tool.ty.terminal]
error-on-warning = true
output-format = "concise"
```

検証 command:

```console
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| Ruff format | 全 Python ファイルが format 済み | `uv run ruff format --check .` | 成功 |
| Ruff lint | 拡張 rule set で lint する | `uv run ruff check .` | 成功 |
| ty | `src` と `tests` を型チェックする | `uv run ty check --no-progress` | 成功 |
| pytest | unit test を実行する | `uv run pytest tests/unit` | 5 passed |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| CI | GitHub Actions で Ruff / ty / pytest を実行する | 実機なし | CI が成功する |
| Git hooks | pre-push で Ruff / ty / pytest を実行する | `.githooks` 有効化済み | hook が成功する |

## 6. 実装チェックリスト

- [x] Ruff の rule set を拡張する
- [x] docstring 系 rule は Google style を採用する
- [x] Google convention と対立する `D203` / `D213` を無効化する
- [x] `PLR` を除外し、`PLC` / `PLE` / `PLW` を採用する
- [x] `tests/**/*.py` で `D100` / `D103` / `S101` を ignore する
- [x] `src/py3dscapture/tools/**/*.py` で `T201` を ignore する
- [x] `flake8-type-checking.strict = true` を設定する
- [x] `known-first-party = ["py3dscapture"]` を設定する
- [x] ty の対象を `src` と `tests` にする
- [x] ty warning を error 扱いにする
- [x] CI / README / AGENTS / PR template の command を更新する
- [x] `uv run ruff format --check .` を実行する
- [x] `uv run ruff check .` を実行する
- [x] `uv run ty check --no-progress` を実行する
- [x] `uv run pytest tests/unit` を実行する

検証結果:

```text
uv run ruff format --check . -> passed
uv run ruff check . -> passed
uv run ty check --no-progress -> passed
uv run pytest tests/unit -> 5 passed
```
