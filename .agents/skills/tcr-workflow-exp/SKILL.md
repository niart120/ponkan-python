---
name: tcr-workflow-exp
description: "test && commit || revert を隔離 worktree 上で試す実験 workflow skill。USE WHEN: ユーザが明示的に TCR、test && commit || revert、TCR実験、tcr-workflow-exp を求めるとき。通常の TDD workflow では暗黙的に使わない。"
---

# TCR Workflow Exp

TCR は `test && commit || revert` を小さい increment で試す実験 workflow として扱う。失敗時の revert は本体作業ツリーではなく、`.worktrees/tcr-workflow-exp/` 配下の隔離 worktree に閉じ込める。

この skill は通常の TDD / Agentic SDD の branch policy ではなく、破壊的 revert を隔離するための例外である。ユーザが TCR を明示していない通常作業では使わない。

## Preconditions

- ユーザが TCR を明示的に要求している。
- 対象は一時 branch / 一時 worktree で進められる。
- 失敗時に捨ててよい increment だけを扱う。
- 実行する test command が短時間で終わる。
- raw `git reset --hard`、`git clean`、`git checkout --` は Codex shell で直接実行しない。

## Harness

TCR 操作には bundled script を使う。

```console
uv run python .agents/skills/tcr-workflow-exp/scripts/tcr_workflow_exp.py init --name spike-001
uv run python .agents/skills/tcr-workflow-exp/scripts/tcr_workflow_exp.py status --worktree .worktrees/tcr-workflow-exp/spike-001
uv run python .agents/skills/tcr-workflow-exp/scripts/tcr_workflow_exp.py cycle --worktree .worktrees/tcr-workflow-exp/spike-001 --message "test: TCR checkpoint" -- uv run pytest tests/unit -q
```

`cycle` は test command が成功した場合だけ隔離 branch に commit する。失敗した場合は隔離 worktree 内の変更だけを直前 commit に戻す。

## Workflow

1. `tdd-test-list` で小さい候補を作る。
2. `init` で `.worktrees/tcr-workflow-exp/{name}` と `tcr-workflow-exp/{name}` branch を作る。
3. 隔離 worktree 内で 1 increment だけ変更する。
4. `cycle` を実行する。
5. 成功したら checkpoint commit を残し、次の increment へ進む。
6. 失敗したら変更は捨てられるため、より小さい increment を選び直す。

## Safety Rules

- 本体作業ツリーで TCR の revert を実行しない。
- `.worktrees/tcr-workflow-exp/` 外の path を harness に渡さない。script は拒否する。
- 失敗時に捨てた内容を復元する前提で進めない。
- TCR branch を通常 branch へ merge する前に、commit history と差分を通常レビューする。
