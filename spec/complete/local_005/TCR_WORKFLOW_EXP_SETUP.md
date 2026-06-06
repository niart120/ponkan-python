# TCR Workflow Exp Setup 仕様書

## 1. 概要

### 1.1 目的

既存の `tcr-lab` skill を `tcr-workflow-exp` に rename し、TCR を本体作業ツリーではなく隔離 worktree 上で実行できる実験 workflow として実装する。Codex hooks の破壊的 git command 禁止は維持し、TCR の `revert` 操作は検査済み script に閉じ込める。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| TCR | `test && commit || revert` の略として扱う。テスト成功時は commit、失敗時は直前の green 状態へ戻す workflow。 |
| revert | TCR において失敗した increment を捨てる操作。git の `revert` command ではなく、作業ツリーを直前の green commit に戻す意味で使う。 |
| 隔離 worktree | `.worktrees/` 配下に作る TCR 専用 git worktree。本体作業ツリーの未コミット変更を巻き込まないための境界。 |
| harness | TCR 操作を安全条件付きで実行する script。Codex が raw `git reset --hard` を直接実行しないための実行境界。 |
| 実験 skill | 通常の `tdd-workflow` には自動接続せず、ユーザが明示的に TCR を求めた場合だけ使う skill。 |

### 1.3 背景・問題

Kent Beck の TCR は、小さい increment を強制し、壊れた状態を長く保持しないための workflow として有用である。一方で、失敗時の `revert` は `git reset --hard` や `git clean` に近い操作になりやすく、AI agent が本体作業ツリーで直接実行するとユーザの未コミット変更を失う危険がある。

現行の `.codex` guardrail は `git reset --hard`、`git clean`、`git checkout --` を禁止している。この禁止を通常 command として緩和するのではなく、TCR 専用 harness が `.worktrees/` 配下の検査済み worktree に限って revert できるようにする。

この仕様は通常の TDD / Agentic SDD に隔離 worktree を要求するものではない。通常の変更作業は作業ブランチ上の通常 worktree で行い、TCR をユーザが明示した場合だけ `.worktrees/tcr-workflow-exp/` 配下の隔離 worktree を使う。

参考文献:

| 種別 | 参照 |
| ---- | ---- |
| TCR | https://medium.com/@kentbeck_7670/test-commit-revert-870bbd756864 |
| Canon TDD | https://tidyfirst.substack.com/p/canon-tdd |
| 日本語翻訳・解説 | https://t-wada.hatenablog.jp/entry/canon-tdd-by-kent-beck |

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| skill 名 | `tcr-lab` | 実験 workflow であることが明確な `tcr-workflow-exp` |
| TCR 実行境界 | 文章上の注意のみ | `.worktrees/` 配下の隔離 worktree を検査する harness |
| 破壊的 git 操作 | raw command は hooks で禁止 | 禁止を維持し、harness 内部だけで限定実行 |
| 失敗時の挙動 | 自動 revert なし | 隔離 worktree 内の変更だけを破棄 |
| 成功時の挙動 | commit は任意 | 隔離 branch 上に TCR checkpoint commit を作る |

### 1.5 着手条件

- [x] `tcr-lab` skill が存在する。
- [x] `.codex` guardrail が破壊的 git command を禁止している。
- [x] `.worktrees/` は git 管理外として扱える。
- [x] `uv run python` で skill script を実行できる。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_005/TCR_WORKFLOW_EXP_SETUP.md` | 新規 | 本仕様書を追加する。 |
| `.agents/skills/tcr-lab/` | 移動 | `.agents/skills/tcr-workflow-exp/` へ rename する。 |
| `.agents/skills/tcr-workflow-exp/SKILL.md` | 修正 | skill 名、利用条件、隔離 worktree workflow、harness 利用手順を更新する。 |
| `.agents/skills/tcr-workflow-exp/agents/openai.yaml` | 修正 | UI metadata を新 skill 名へ更新する。 |
| `.agents/skills/tcr-workflow-exp/scripts/tcr_workflow_exp.py` | 新規 | TCR 用の隔離 worktree init / cycle / status harness を追加する。 |
| `AGENTS.md` | 修正 | `tcr-lab` を `tcr-workflow-exp` に置き換える。 |
| `spec/complete/local_004/TDD_SKILL_WORKFLOW_SETUP.md` | 修正 | 既存仕様上の skill 名を `tcr-workflow-exp` へ追従する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| skill rename | `tcr-lab` が存在する | `tcr-workflow-exp` として参照できる | 旧 skill directory は残さない |
| worktree init | branch 名と `.worktrees/` 配下 path を指定する | 指定 branch の隔離 worktree が作成される | 本体作業ツリーの dirty 状態は破棄しない |
| TCR cycle 成功 | 隔離 worktree で test command が成功する | `git add -A` 後に commit を作る | 変更がない場合は no-op |
| TCR cycle 失敗 | 隔離 worktree で test command が失敗する | 隔離 worktree 内だけを直前 commit に戻す | 本体作業ツリーは触らない |
| unsafe path 拒否 | `.worktrees/` 外の path を指定する | harness が失敗して操作しない | path traversal を拒否する |
| raw destructive command | Codex shell で `git reset --hard` を実行しようとする | 既存 hooks が禁止する | hooks は緩和しない |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | `tcr-lab` を `tcr-workflow-exp` に rename する | new behavior | 3.1 | `git mv` で実施済み |
| green | harness が `.worktrees/` 外 path を拒否する | edge case | 3.1 | smoke test 実行済み |
| green | harness の help / status command が実行できる | new behavior | 3.1 | destructive 操作なしで確認済み |
| green | skill metadata を validate できる | regression | 5 | `quick_validate.py` 通過 |

### 3.3 設計方針

TCR の正式 skill 化ではなく、`exp` suffix を持つ実験 workflow とする。理由は、TCR の失敗時操作が強い破棄 semantics を持つためである。通常の `tdd-workflow` から暗黙的に使わず、ユーザが `TCR`、`test && commit || revert`、`tcr-workflow-exp` を明示した場合だけ使う。

harness は raw destructive git command を Codex shell に露出しない。script 内部では次の条件を満たす場合だけ revert 相当の操作を許可する。

- 対象 path が repository root 配下の `.worktrees/` 内に resolve される。
- 対象 path が git worktree として認識できる。
- script の subcommand が `cycle` であり、test command が失敗した。
- revert 対象は隔離 worktree の worktree-local changes に限定する。

## 4. 実装仕様

### 4.1 skill 構成

```text
.agents/skills/tcr-workflow-exp/
  SKILL.md
  agents/
    openai.yaml
  scripts/
    tcr_workflow_exp.py
```

### 4.2 harness CLI

```console
uv run python .agents/skills/tcr-workflow-exp/scripts/tcr_workflow_exp.py init --name spike-001
uv run python .agents/skills/tcr-workflow-exp/scripts/tcr_workflow_exp.py status --worktree .worktrees/tcr-workflow-exp/spike-001
uv run python .agents/skills/tcr-workflow-exp/scripts/tcr_workflow_exp.py cycle --worktree .worktrees/tcr-workflow-exp/spike-001 --message "test: TCR checkpoint" -- uv run pytest tests/unit -q
```

`init` は `.worktrees/tcr-workflow-exp/{name}` を作成し、branch は `tcr-workflow-exp/{name}` を既定値とする。`cycle` は test command 成功時に commit し、失敗時に隔離 worktree だけを revert する。

### 4.3 hook 方針

`.codex` の command 禁止は緩和しない。将来緩和する場合も、raw `git reset --hard` を許可するのではなく、`uv run python .agents/skills/tcr-workflow-exp/scripts/tcr_workflow_exp.py ...` のような検査済み harness 実行だけを許可候補にする。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| skill frontmatter | 新 skill 名が validate される | `quick_validate.py .agents/skills/tcr-workflow-exp` | validate が成功する |
| harness help | CLI が起動する | `uv run python ... --help` | usage が表示される |
| unsafe path | `.worktrees/` 外 path を拒否する | `status --worktree .` | 非 0 で失敗する |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| project lint | script 追加後の lint | `uv` dev 環境 | `uv run ruff check .` が成功する |
| skill smoke | skill script の help と status failure | Python 3.12+ | destructive 操作なしで検証できる |

### 検証コマンド

```console
uv run --with pyyaml python -X utf8 C:\Users\train\.codex\skills\.system\skill-creator\scripts\quick_validate.py .agents\skills\tcr-workflow-exp
uv run python .agents/skills/tcr-workflow-exp/scripts/tcr_workflow_exp.py --help
uv run python .agents/skills/tcr-workflow-exp/scripts/tcr_workflow_exp.py status --worktree .
uv run ruff check .
uv run ruff format --check .
```

## 6. 実装チェックリスト

- [x] 本仕様書を作成する。
- [x] 本仕様書を単独 commit する。
- [x] `tcr-lab` を `tcr-workflow-exp` に rename する。
- [x] `SKILL.md` を `tcr-workflow-exp` 向けに更新する。
- [x] `agents/openai.yaml` を更新する。
- [x] `scripts/tcr_workflow_exp.py` を追加する。
- [x] `AGENTS.md` と `local_004` 仕様を rename 後の skill 名へ追従する。
- [x] skill-creator の `quick_validate.py` で skill を検証する。
- [x] harness の help / unsafe path smoke test を実行する。
- [x] `uv run ruff check .` を実行する。
- [x] `uv run ruff format --check .` を実行する。
- [x] 実装差分を commit する。
