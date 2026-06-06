# Git Context Policy 仕様書

更新日: 2026-06-07

## 1. 概要

### 1.1 目的

`local_004` から `local_006` で追加した TDD、TCR、Agentic SDD、PR merge skill 群について、GitHub Flow を project policy として採用し、git branch / git worktree の責務を明確にする。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| Git Context Gate | 変更前に現在 branch、default branch、worktree dirty 状態、TCR 要否を確認する gate。 |
| GitHub Flow | default branch から短命な作業ブランチを作り、PR 経由で default branch に merge する運用。 |
| 作業ブランチ | `master` / `main` などの default branch ではない通常の実装 branch。 |
| 通常 worktree | repo root の現在作業ツリー。TDD / Agentic SDD の通常作業で使う。 |
| 隔離 worktree | `.worktrees/` 配下に作る一時 worktree。TCR の revert 境界として使う。 |
| default branch | `master` / `main` など、PR merge 先になる branch。 |

### 1.3 背景・問題

`tcr-workflow-exp` は隔離 worktree 前提だが、通常の TDD / Agentic SDD skill は現在 worktree を確認するだけで、変更を伴う作業を default branch 上で始めるかどうかが曖昧だった。

一方で `pr-merge-cleanup` は作業ブランチ前提である。これにより、実装開始時の branch 作成責務と PR merge 時の branch 前提の間に隙間があった。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| default branch 保護 | 個別判断 | 変更を伴う Work Unit は作業ブランチ上で開始する |
| GitHub Flow | 暗黙運用 | 短命な作業ブランチ、PR、merge commit、merge 後 cleanup を明文化する |
| TDD / Agentic SDD | 通常 worktree だが branch 方針が曖昧 | 通常 worktree + 作業ブランチを既定にする |
| TCR | 隔離 worktree 前提 | 通常 workflow と明確に分離する |
| PR merge | 作業ブランチ前提 | Agentic SDD の Git Context Gate から自然につながる |

### 1.5 着手条件

- [x] `local_004` の TDD skill 群が存在する。
- [x] `local_005` の `tcr-workflow-exp` が存在する。
- [x] `local_006` の `agentic-sdd` / `agentic-self-review` が存在する。
- [x] `pr-merge-cleanup` が merge commit 既定へ更新済みである。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/complete/local_007/GIT_CONTEXT_POLICY.md` | 新規 | Git Context Gate の仕様を追加する。 |
| `spec/complete/local_004/TDD_SKILL_WORKFLOW_SETUP.md` | 修正 | TDD skill 群は隔離 worktree 必須ではなく、作業ブランチで行う方針を追記する。 |
| `spec/complete/local_005/TCR_WORKFLOW_EXP_SETUP.md` | 修正 | TCR が隔離 worktree を要求する例外であることを追記する。 |
| `spec/complete/local_006/AGENTIC_SPEC_DRIVEN_DEVELOPMENT.md` | 修正 | Git Context Gate を Agentic SDD の gate として追加する。 |
| `spec/complete/local_006/AGENT_BOOTSTRAP_PLAYBOOK.md` | 修正 | bootstrap 出力と Main Agent 責務に branch / status 確認を追加する。 |
| `spec/complete/local_006/QUALITY_GATES_AND_REVIEW.md` | 修正 | Gate 階層と report template に Git Context を追加する。 |
| `AGENTS.md` | 修正 | project-level Git context policy を追加する。 |
| `.agents/skills/agentic-sdd/SKILL.md` | 修正 | Git Context Gate を bootstrap と Plan に追加する。 |
| `.agents/skills/tdd-workflow/SKILL.md` | 修正 | 通常 TDD の branch 前提を追記する。 |
| `.agents/skills/tdd-one-cycle/SKILL.md` | 修正 | 1 cycle 実行前の git context 前提を追記する。 |
| `.agents/skills/tcr-workflow-exp/SKILL.md` | 修正 | TCR は通常 branch policy ではなく隔離 worktree 例外であることを追記する。 |
| `.agents/skills/pr-merge-cleanup/SKILL.md` | 修正 | PR merge は Git Context Gate 済みの作業ブランチを入力にすることを追記する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| Git context を確認する | 変更を伴う Work Unit を開始する | 現在 branch、default branch、dirty 状態を確認する | read-only 調査では省略可 |
| GitHub Flow で進める | 変更を default branch へ入れる | 作業ブランチ、PR、merge commit、merge 後 cleanup の順に進める | squash merge はユーザ明示時のみ |
| default branch 上の変更を避ける | `master` / `main` 上で変更を伴う作業を開始する | 作業ブランチを作るか、既存作業ブランチへ切り替える | ユーザが明示した場合を除く |
| dirty worktree を保護する | 未コミット変更がある | 既存変更を読んで作業可否を判断し、無断で破棄しない | ユーザ変更を守る |
| TCR を隔離する | ユーザが TCR を明示する | `.worktrees/tcr-workflow-exp/` 配下の隔離 worktree を使う | 通常 TDD では使わない |
| PR merge を作業ブランチから行う | PR merge cleanup を開始する | default branch 上なら中断する | merge 後に default branch へ同期する |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | `agentic-sdd` が Work Unit 開始時に branch / status を確認する | regression | 3.1 | skill と `AGENTS.md` に反映 |
| green | 通常 TDD は隔離 worktree を要求しない | regression | 3.1 | `tdd-workflow` に反映 |
| green | TCR は隔離 worktree を要求する例外として残る | regression | 3.1 | `tcr-workflow-exp` に反映 |
| green | PR merge cleanup は作業ブランチ前提を維持する | regression | 3.1 | `pr-merge-cleanup` に反映 |

### 3.3 設計方針

Git context は新しい実装 framework ではなく、既存 workflow の境界条件として扱う。Agentic SDD が実装開始時に確認し、TDD skill はその context を前提に red / green / refactor を進める。

GitHub Flow は project の標準 git 運用として扱う。変更は短命な作業ブランチで行い、PR 経由で default branch に取り込む。PR merge は `pr-merge-cleanup` の merge commit 既定に従い、merge 後に default branch 同期と branch cleanup まで完了させる。

TCR は破壊的 revert を伴うため通常 workflow に混ぜない。`tcr-workflow-exp` をユーザが明示した場合だけ隔離 worktree を作る。

## 4. 実装仕様

Git Context Gate:

```text
- current branch: git branch --show-current
- default branch: origin/HEAD or project default
- status: git status --short
- action:
  - read-only: current branch ok
  - write on non-default clean branch: continue
  - write on default clean branch: create/switch work branch
  - dirty worktree: inspect and protect existing changes
  - TCR: use .worktrees/tcr-workflow-exp/
```

GitHub Flow:

```text
- start from default branch or current integration base
- create/switch a short-lived work branch
- commit with Conventional Commits
- open PR from work branch to default branch
- merge with merge commit by default
- sync default branch after merge
- delete local and remote work branch
```

branch 名は作業内容から短く決める。例:

```text
chore/git-context-policy
feat/n3dsxl-device-listing
test/n3dsxl-sizes
```

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| skill frontmatter | 更新した skill が valid | `quick_validate.py .agents/skills/agentic-sdd` | validate が成功する |
| skill frontmatter | TDD / TCR / PR skill が valid | `quick_validate.py .agents/skills/tdd-workflow` | validate が成功する |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| ドキュメント更新 | Markdown の trailing whitespace がない | `git diff --check` | 成功する |
| project validation | Python hook / skill 変更が既存検証を壊さない | `uv` dev 環境が利用可能 | `ruff check` が成功する |

### 検証コマンド

```console
git diff --check
uv run ruff check .
```

## 6. 実装チェックリスト

- [x] Git Context Gate 仕様を作成する。
- [x] GitHub Flow 採用方針を project policy として明文化する。
- [x] `local_004` 仕様に通常 TDD と branch 方針を追記する。
- [x] `local_005` 仕様に TCR が隔離 worktree 例外であることを追記する。
- [x] `local_006` 仕様に Git Context Gate を追記する。
- [x] `AGENTS.md` に project-level Git context policy を追記する。
- [x] `agentic-sdd` skill を更新する。
- [x] `tdd-workflow` / `tdd-one-cycle` skill を更新する。
- [x] `tcr-workflow-exp` skill を更新する。
- [x] `pr-merge-cleanup` skill を更新する。
- [x] skill validation と静的検証を実行する。
- [x] レビュー完了。

検証結果:

```text
git diff --check -> passed
uv run ruff check . -> All checks passed!
uv run python -X utf8 C:\Users\train\.codex\skills\.system\skill-creator\scripts\quick_validate.py .agents\skills\agentic-sdd -> Skill is valid!
uv run python -X utf8 C:\Users\train\.codex\skills\.system\skill-creator\scripts\quick_validate.py .agents\skills\tdd-workflow -> Skill is valid!
uv run python -X utf8 C:\Users\train\.codex\skills\.system\skill-creator\scripts\quick_validate.py .agents\skills\tdd-one-cycle -> Skill is valid!
uv run python -X utf8 C:\Users\train\.codex\skills\.system\skill-creator\scripts\quick_validate.py .agents\skills\tcr-workflow-exp -> Skill is valid!
uv run python -X utf8 C:\Users\train\.codex\skills\.system\skill-creator\scripts\quick_validate.py .agents\skills\pr-merge-cleanup -> Skill is valid!
```
