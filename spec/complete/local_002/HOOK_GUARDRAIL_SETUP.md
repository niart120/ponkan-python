# Git Hooks・Codex Command Guardrail 仕様書

## 1. 概要

### 1.1 目的

`ponkan-python` の commit / push / commit message を Git hooks で制御し、Codex による生 Python command と危険な Git command の実行を project-local policy で抑止する。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| Git hooks | Git が commit / push などの lifecycle で実行する hook。 |
| tracked hooks | `.githooks/` に配置し Git 管理する hook 本体。 |
| `core.hooksPath` | Git が hooks directory として参照する local config。 |
| Codex rules | `.codex/rules/*.rules` に置く Codex command 実行 policy。 |
| Codex hooks | `.codex/hooks.json` から起動する Codex lifecycle hook。 |
| 生 Python command | `python` / `python3` / `py` / `pip` / `pytest` / `ruff` / `ty` を `uv` 経由せず直接実行する command。 |
| 破壊的 Git command | 未コミット変更や untracked file を捨てる `git reset --hard`、`git clean`、`git checkout -- <path>`。 |

### 1.3 背景・問題

Python 実行を `uv` に統一する規約は `AGENTS.md` にあるが、mechanical enforcement がなかった。Git hooks は `.git/hooks` へ置くと Git 管理できないため、clone 後に再現できる tracked hooks と有効化手順が必要だった。Codex についても、project-local hooks / rules によって生 Python command と破壊的 Git command を抑止する必要があった。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| commit 前検証 | 手動実行 | `pre-commit` で lock / format / lint を実行 |
| push 前検証 | 手動実行 | `pre-push` で lock / format / lint / type / unit test を実行 |
| commit message | 手動確認 | `commit-msg` で Conventional Commits と日本語 subject を検査 |
| Codex command policy | AGENTS.md 依存 | `.codex/rules` と `PreToolUse` hook で抑止 |

### 1.5 着手条件

- [x] `ruff` / `ty` / `pytest` の設定が `pyproject.toml` に存在する
- [x] `uv.lock` が存在する
- [x] Git 2.49.0 で `core.hooksPath` と `git hook run` を利用できる
- [x] Codex manual で project-local hooks / rules の配置を確認する

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `.githooks/pre-commit` | 新規 | `uv lock --check`、`ruff format --check`、`ruff check` を実行する |
| `.githooks/pre-push` | 新規 | pre-commit 相当、`ty check`、`pytest tests/unit` を実行する |
| `.githooks/commit-msg` | 新規 | Conventional Commits、日本語 subject、末尾句点なしを検査する |
| `.githooks/README.md` | 新規 | tracked hooks の有効化手順を記載する |
| `scripts/install-git-hooks.ps1` | 新規 | Windows 用 hook 有効化 script を追加する |
| `scripts/install-git-hooks.sh` | 新規 | POSIX shell 用 hook 有効化 script を追加する |
| `.codex/rules/default.rules` | 新規 | 生 Python command と破壊的 Git command を禁止する |
| `.codex/hooks.json` | 新規 | `PreToolUse` hook を登録する |
| `.codex/hooks/pre_tool_use_policy.py` | 新規 | Codex hook payload 内の command string を検査する |
| `.codex/hooks/run-pre-tool-use-policy.ps1` | 新規 | Windows 用 Codex hook wrapper を追加する |
| `.codex/README.md` | 新規 | Codex project-local policy の有効化条件を記載する |
| `README.md` | 修正 | clone 後の hook 有効化手順を追記する |

## 3. 設計方針

Git hooks は `.git/hooks` ではなく `.githooks/` を正本にする。Git は clone 時に tracked hooks を自動有効化しないため、`core.hooksPath` を local config として設定する手順を必須にする。

Codex の単純な command 禁止は `.codex/rules/default.rules` に置く。Rules は静的で副作用がなく、`codex execpolicy check` で検証できるため、`python` / `pip` / `pytest` / `ruff` / `ty` の直実行禁止に向く。`PreToolUse` hook は、Codex が tool payload を渡す環境で command string を追加検査する補助線として扱う。

破壊的 Git command の禁止は `git commit` ではなく、作業ツリーを破棄する操作を対象にする。具体的には `git reset --hard`、`git clean`、`git checkout -- <path>` を禁止対象にする。

## 4. 実装仕様

clone 後の Git hooks 有効化手順:

```console
git config core.hooksPath .githooks
```

または:

```console
scripts/install-git-hooks.ps1
sh scripts/install-git-hooks.sh
```

Git hooks の実行内容:

```console
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

Codex rules の代表例:

```python
prefix_rule(
    pattern = ["python"],
    decision = "forbidden",
    justification = "Use `uv run python ...` so the project environment is used.",
)
```

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| Codex hook policy | 生 Python command を拒否する | `{"command":"python script.py"}` | exit code 1 |
| Codex hook policy | `uv run python` を許可する | `{"command":"uv run python script.py"}` | exit code 0 |
| Codex hook policy | `git reset --hard` を拒否する | `{"command":"git reset --hard"}` | exit code 1 |
| commit-msg hook | 日本語 Conventional Commit を許可する | `chore: hook制御を追加` | exit code 0 |
| commit-msg hook | 英語のみ subject を拒否する | `chore: add hooks` | exit code 1 |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| pre-commit | lock / format / lint を実行する | `core.hooksPath=.githooks` | hook が成功する |
| pre-push | lock / format / lint / type / unit test を実行する | `core.hooksPath=.githooks` | hook が成功する |
| Codex rules | `codex execpolicy check` で禁止 command を検出する | Codex CLI が利用可能 | `decision = forbidden` |

## 6. 実装チェックリスト

- [x] `.githooks/pre-commit` を追加する
- [x] `.githooks/pre-push` を追加する
- [x] `.githooks/commit-msg` を追加する
- [x] hook 有効化 script を追加する
- [x] `.codex/rules/default.rules` を追加する
- [x] `.codex/hooks.json` と hook script を追加する
- [x] `.githooks/README.md` と install script で `git config core.hooksPath .githooks` を案内する
- [x] 破壊的 Git command の定義を本仕様書に明記する
- [x] `git hook run pre-commit` を実行する
- [x] `git hook run pre-push` を実行する
- [x] `git hook run commit-msg` を valid / invalid message で検証する
- [x] `codex execpolicy check` を forbidden / allowed command で検証する
- [x] `uv run ruff format --check .` を実行する
- [x] `uv run ruff check .` を実行する
- [x] `uv run ty check --no-progress` を実行する
- [x] `uv run pytest tests/unit` を実行する

検証結果:

```text
git hook run pre-commit -> passed
git hook run pre-push -> passed
git hook run commit-msg -- valid message -> passed
git hook run commit-msg -- invalid message -> rejected
codex execpolicy check -- python script.py -> forbidden
codex execpolicy check -- uv run python script.py -> allowed
codex execpolicy check -- git reset --hard -> forbidden
uv run ruff format --check . -> passed
uv run ruff check . -> passed
uv run ty check --no-progress -> passed
uv run pytest tests/unit -> 5 passed
```
