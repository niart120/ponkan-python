# Codex Project Policy

このディレクトリは ponkan-python 用の Codex project-local 設定です。

## 有効化条件

Codex は project `.codex/` layer が trusted の場合だけ、project-local hooks と rules を読み込みます。新しい hook や変更された hook は `/hooks` で内容を確認して trust する必要があります。

## 内容

- `rules/default.rules`: 生 `python` / `pip` / `pytest` / `ruff` / `ty` と破壊的 Git command を禁止する静的 policy。
- `hooks.json`: `PreToolUse` で `Bash` command を検査する hook。
- `hooks/pre_tool_use_policy.py`: stdin payload に含まれる command string を走査し、禁止 command を検出する。

## 注意

Codex hooks は Git hooks とは別物です。Git commit / push の制御は `.githooks/` を使います。
