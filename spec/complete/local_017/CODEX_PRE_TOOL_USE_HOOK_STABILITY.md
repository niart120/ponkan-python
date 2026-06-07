# Codex PreToolUse Hook Stability 仕様書

更新日: 2026-06-08

## 1. 概要

### 1.1 目的

`ponkan-python` の Codex `PreToolUse` hook が Windows sandbox 上で安定して起動し、禁止 command を policy として確実に block できるようにする。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| `PreToolUse` hook | Codex が tool 実行前に呼び出す lifecycle hook。 |
| `commandWindows` | Codex hook handler の Windows 専用 command override。 |
| repo-local uv cache | repository の作業ツリー内に置く uv cache。本仕様では `.uv-cache`。 |
| policy block | `pre_tool_use_policy.py` が command payload を拒否し、exit code `2` を返す状態。 |
| hook 異常終了 | policy 判定に到達せず、shell quoting、stdin forwarding、cache access などで hook runner が失敗する状態。 |
| worktree | Git が同一 repository から checkout する作業ツリー。通常 branch 作業や隔離作業で使う。 |

### 1.3 背景・問題

`local_002` で Codex command guardrail を導入したが、Windows 上の `commandWindows` が PowerShell 変数の quote / escape に依存していた。Codex の実行経路によっては `$root` が期待どおり評価されず、`Join-Path` が対話 prompt を出す、または hook が異常終了する問題があった。

また、Codex Windows sandbox から `%LOCALAPPDATA%\uv\cache` を読めず、`uv run python` が `sdists-v9\.git` の access denied で失敗する場合があった。この失敗は hook policy 以前の起動失敗であり、禁止 command の block と区別する必要があった。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| Windows hook 起動 | shell 経路により `$root` / `Join-Path` が壊れる | `commandWindows` が shell quote に依存せず wrapper を起動する |
| policy block | hook 異常終了と区別しづらい | 禁止 command は exit code `2` と policy message で失敗する |
| allowed command | uv cache access denied で hook が落ちる場合がある | repo-local uv cache により allowed command は exit code `0` になる |
| worktree 利用 | global uv cache または cwd 相対 cache に依存する | 各 worktree の repo root 配下 `.uv-cache` を使う |

### 1.5 着手条件

- [x] `.codex/hooks.json` に `PreToolUse` hook が存在する。
- [x] `.codex/hooks/pre_tool_use_policy.py` が stdin payload を検査する。
- [x] Windows 用 wrapper `.codex/hooks/run-pre-tool-use-policy.ps1` が存在する。
- [x] Codex Windows sandbox で `%LOCALAPPDATA%\uv\cache` access denied が再現している。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `.codex/hooks.json` | 修正 | `commandWindows` を `-EncodedCommand` 形式に変更し、PowerShell 変数の quote / escape 依存を避ける。 |
| `.codex/hooks/run-pre-tool-use-policy.ps1` | 修正 | hook 実行時に repo root へ移動し、`UV_CACHE_DIR` を repo root の `.uv-cache` に固定する。 |
| `pyproject.toml` | 修正 | `[tool.uv] cache-dir = ".uv-cache"` を追加し、repo root からの通常 `uv run` が repo-local cache を使うようにする。 |
| `.gitignore` | 修正 | `.uv-cache/` を ignore 対象に追加する。 |
| `spec/complete/local_017/CODEX_PRE_TOOL_USE_HOOK_STABILITY.md` | 新規 | 本修正仕様を記録する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| allowed command を許可する | `{"command":"git status --short"}` | hook が exit code `0` を返す | `cmd` 経由、PowerShell 直、subdir cwd で検証する。 |
| 生 Python command を拒否する | `{"command":"python script.py"}` | policy message を出し exit code `2` を返す | hook 異常終了ではなく policy block として扱う。 |
| 実機 command を承認なしで拒否する | `{"command":"uv run pytest -m requires_n3dsxl tests/e2e"}` | policy message を出し exit code `2` を返す | 実機は実行しない。payload 検査のみ。 |
| 実機 command を承認付きで許可する | `{"command":"$env:PONKAN_HARDWARE_APPROVED=1; uv run pytest -m requires_n3dsxl tests/e2e"}` | hook が exit code `0` を返す | command 実行前 hook の許可確認だけを行う。 |
| repo-local cache を使う | repo root から `uv run python --version` を実行 | `%LOCALAPPDATA%` ではなく `.uv-cache` を使い exit code `0` になる | cold cache の初回 populate は network が必要。 |
| worktree ごとの cache を使う | 別 worktree で同じ tracked config を使う | その worktree の `.uv-cache` が使われる | `.uv-cache/` は Git 管理しない。 |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | `cmd` 経由の allowed payload が exit code `0` になる | regression | 3.1 | `commandWindows` の実行経路を再現。 |
| green | `cmd` 経由の forbidden payload が exit code `2` になる | regression | 3.1 | `python script.py` を payload とする。 |
| green | PowerShell 直の forbidden payload が exit code `2` になる | regression | 3.1 | `-EncodedCommand` を直接実行。 |
| green | subdir cwd の hook 実行でも repo root cache を使う | regression | 3.1 | `src/py3dscapture` から検証。 |
| green | 通常 gate が repo-local cache 設定後も通る | regression | 5 | ruff / ty / pytest を実行。 |

### 3.3 設計方針

`commandWindows` は shell の quote / escape 差に影響されやすいため、短い PowerShell script を UTF-16LE Base64 の `-EncodedCommand` として登録する。Encoded script は git root を解決し、Windows wrapper を `powershell -File` で呼び、最後に `$LASTEXITCODE` を返す。

Windows wrapper は hook policy script の実行前に repo root へ移動する。さらに `UV_CACHE_DIR` を repo root 配下の `.uv-cache` の絶対 path に設定し、Codex Windows sandbox が読めない user global uv cache を使わない。

`pyproject.toml` の `cache-dir = ".uv-cache"` は repo root からの通常 `uv run` を安定化するために置く。ただし uv 0.7.13 では相対 `cache-dir` が実行 cwd 相対として解釈されるため、subdir からの plain `uv run` まで保証しない。hook は wrapper 側で root へ移動するためこの制約を受けない。

## 4. 実装仕様

Windows hook command は、概念的に次の script を実行する。

```powershell
$ProgressPreference = 'SilentlyContinue'
$root = git rev-parse --show-toplevel
$hook = Join-Path $root '.codex/hooks/run-pre-tool-use-policy.ps1'
powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $hook
exit $LASTEXITCODE
```

wrapper は stdin payload を保持したまま policy script を実行する。

```powershell
$ErrorActionPreference = "Stop"

$repoRoot = git rev-parse --show-toplevel
$scriptPath = Join-Path $repoRoot ".codex/hooks/pre_tool_use_policy.py"
$payload = [Console]::In.ReadToEnd()

Set-Location -LiteralPath $repoRoot
$env:UV_CACHE_DIR = Join-Path $repoRoot ".uv-cache"
$payload | uv run python $scriptPath
exit $LASTEXITCODE
```

uv cache 設定:

```toml
[tool.uv]
cache-dir = ".uv-cache"
```

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| `pre_tool_use_policy.py` | 生 Python command を拒否する | `python script.py` | exit code `2` |
| `pre_tool_use_policy.py` | 実機 marker command を承認なしで拒否する | `uv run pytest -m requires_n3dsxl tests/e2e` | exit code `2` |
| `pre_tool_use_policy.py` | 実機承認 flag 付き command を許可する | `$env:PONKAN_HARDWARE_APPROVED=1; ...` | exit code `0` |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| Windows hook command | `hooks.json` の `commandWindows` を `cmd` 経由で実行する | repo root cwd | allowed は `0`、forbidden は `2` |
| subdir hook command | `src/py3dscapture` cwd から hook を実行する | Git root が解決可能 | allowed は `0`、forbidden は `2` |
| repo-local uv cache | repo root から `uv run python --version` を実行する | `.uv-cache` が作成可能 | exit code `0` |
| full gate | 既存 lint / type / unit test を実行する | dev 環境が synced | すべて成功 |

### 検証コマンド

```console
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

追加で次の hook payload 再現を実行する。

```console
# allowed payload
{"tool_name":"Bash","tool_input":{"command":"git status --short"}}

# forbidden payload
{"tool_name":"Bash","tool_input":{"command":"python script.py"}}
```

検証結果:

```text
cmd 経由 allowed -> exit 0
cmd 経由 blocked -> exit 2
PowerShell 直 allowed -> exit 0
PowerShell 直 blocked -> exit 2
subdir cwd の hook allowed / block -> OK
uv run python --version -> OK
uv run ruff format --check . -> passed
uv run ruff check . -> passed
uv run ty check --no-progress -> passed
uv run pytest tests/unit -> 81 passed
pre-commit hook -> uv lock --check / ruff format / ruff check passed
```

## 6. 実装チェックリスト

- [x] Codex `commandWindows` の `$root` / `Join-Path` 失敗を再現する。
- [x] uv global cache access denied を再現する。
- [x] repo-local `.uv-cache` 設定を追加する。
- [x] `.uv-cache/` を `.gitignore` に追加する。
- [x] Windows hook wrapper で repo root へ移動する。
- [x] Windows hook wrapper で `UV_CACHE_DIR` を repo root 配下に固定する。
- [x] `commandWindows` を `-EncodedCommand` に変更する。
- [x] allowed / forbidden payload の exit code を検証する。
- [x] subdir cwd からの hook 実行を検証する。
- [x] `uv run ruff format --check .` を実行する。
- [x] `uv run ruff check .` を実行する。
- [x] `uv run ty check --no-progress` を実行する。
- [x] `uv run pytest tests/unit` を実行する。
- [x] `fix(codex): PreToolUse hook の Windows 実行を安定化` として実装修正を commit する。
- [x] 本仕様書を作成する。

運用上の注意:

- `.codex/hooks.json` を変更したため、Codex 側では `/hooks` で再 review / trust が必要になる。
- cold cache の worktree では、初回 `uv sync --dev` または必要な `uv run` が network を必要とする場合がある。
- subdir から plain `uv run` を直接実行する場合は cwd 相対 cache の影響を受ける可能性がある。必要に応じて `uv --directory <repo-root> run ...` を使う。
