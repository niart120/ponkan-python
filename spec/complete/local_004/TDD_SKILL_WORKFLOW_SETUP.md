# TDD Skill Workflow Setup 仕様書

## 1. 概要

### 1.1 目的

Kent Beck の Canon TDD を ponkan-python の agent skill として実行可能な手順に分解し、既存の `spec-format` と接続する。実開発前の AI Agent 環境に、テストリスト、1サイクル実行、Tidy First、Test Desiderata レビューを扱う skill 群を追加する。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| Canon TDD | テストリストを作り、1項目だけを実行可能テストへ変換し、通してから必要に応じてリファクタリングする Kent Beck の TDD workflow。 |
| テストリスト | 期待する振る舞い、variant、既存動作の回帰リスクを、実装設計と分けて列挙した作業リスト。 |
| Red / Green / Refactor | 失敗するテストを確認し、最小変更で成功させ、成功状態で設計を改善する TDD の状態遷移。 |
| Tidy First | 振る舞い変更と構造変更を分け、必要な構造改善をいつ行うか判断する設計方針。 |
| Test Desiderata | テストの価値を複数の望ましい性質の trade-off としてレビューする Kent Beck の観点。 |
| TCR | `test && commit || revert` に由来する実験的 workflow。破壊的 git 操作を伴うため、この仕様では補助 skill として扱う。 |

### 1.3 背景・問題

現在の `.agents/skills` には仕様書、原典 audit、実機 harness などの skill があるが、実装時に TDD を一貫して支える skill はない。`AGENTS.md` には t_wada 氏の TDD 指針を意識する方針があるものの、agent がどのタイミングでテストリストを作り、どの粒度で red/green/refactor を進め、構造変更をどう切り分けるかは未定義である。

参考文献:

| 種別 | 参照 |
| ---- | ---- |
| 原典 workflow | https://tidyfirst.substack.com/p/canon-tdd |
| 日本語翻訳・解説 | https://t-wada.hatenablog.jp/entry/canon-tdd-by-kent-beck |
| Test Desiderata | https://kentbeck.github.io/TestDesiderata/ |
| 構造変更と振る舞い変更 | https://tidyfirst.substack.com/p/structure-and-behavior |
| TCR | https://medium.com/@kentbeck_7670/test-commit-revert-870bbd756864 |
| TDD by Example | https://www.oreilly.com/library/view/test-driven-development/0321146530/ |
| Tidy First? | https://www.oreilly.com/library/view/tidy-first/9781098151232/ |

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| TDD 手順の明示性 | `AGENTS.md` の方針のみ | skill metadata と `SKILL.md` で利用条件と手順を明文化する |
| 仕様とテストリストの接続 | 個別判断 | `spec-format` template に振る舞い仕様と TDD Test List を追加する |
| 構造変更の混入防止 | 個別判断 | `tidy-first` skill で behavior / structure の変更種別を分ける |
| テスト品質レビュー | 未整備 | `test-desiderata-review` skill で trade-off を確認する |
| TCR の扱い | 未定義 | 破壊的 git guardrail と衝突しない補助 skill として明記する |

### 1.5 着手条件

- [x] `.agents/skills` を project-local skill の正本として扱う方針がある。
- [x] `spec-format` skill と template が存在する。
- [x] `ruff` / `ty` / `pytest` の基本検証コマンドが定義されている。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_004/TDD_SKILL_WORKFLOW_SETUP.md` | 新規 | 本仕様書を追加する。 |
| `.agents/skills/spec-format/SKILL.md` | 修正 | TDD Test List と振る舞い仕様の接続を記述する。 |
| `.agents/skills/spec-format/references/template.md` | 修正 | `振る舞い仕様`、`TDD Test List`、`検証コマンド` を追加する。 |
| `.agents/skills/tdd-workflow/SKILL.md` | 新規 | TDD skill 群の orchestrator を追加する。 |
| `.agents/skills/tdd-test-list/SKILL.md` | 新規 | 振る舞いベースのテストリスト作成 skill を追加する。 |
| `.agents/skills/tdd-one-cycle/SKILL.md` | 新規 | 1項目分の red/green/refactor 実行 skill を追加する。 |
| `.agents/skills/tidy-first/SKILL.md` | 新規 | behavior / structure 変更分離 skill を追加する。 |
| `.agents/skills/test-desiderata-review/SKILL.md` | 新規 | Test Desiderata に基づくテストレビュー skill を追加する。 |
| `.agents/skills/tcr-workflow-exp/SKILL.md` | 新規 | 任意の実験用 TCR skill を追加し、通常 workflow からは外す。 |
| `AGENTS.md` | 修正 | 主要 skill 一覧に TDD 関連 skill を追加する。 |

## 3. 設計方針

TDD の workflow step と skill は 1:1 対応に固定しない。実装中の agent が使いやすい単位を優先し、全体 orchestration、テストリスト作成、1サイクル実行、構造変更判断、テスト品質レビューに分ける。

`tdd-workflow` は入口 skill とし、仕様書が関係する作業では `spec-format` を先に使う。`tdd-test-list` は Canon TDD の最初の分析段階を担当し、実装設計ではなく振る舞いの variant を扱う。`tdd-one-cycle` は 1項目だけを runnable test に変換し、red を確認してから green にし、必要な場合だけ refactor へ進む。`tidy-first` は refactor と事前 tidy の判断を扱い、振る舞い変更と構造変更を同じ目的として混ぜない。`test-desiderata-review` はテストの価値を、fast / readable / behavioral / structure-insensitive / deterministic などの trade-off として見る。

`tcr-workflow-exp` は通常の開発 workflow には組み込まない。現在の Codex policy は `git reset --hard` などの破壊的 git 操作を禁止しているため、TCR は安全な一時 branch / worktree と明示承認がある場合に限る。

Git context は Agentic SDD の Git Context Gate に従う。通常の TDD skill 群は隔離 worktree を要求しないが、変更を伴う red / green / refactor は default branch ではなく作業ブランチ上で行う。default branch 上で変更を始める場合は、read-only 調査やユーザの明示指示を除き、先に作業ブランチを作る。TCR だけは通常 branch policy ではなく `tcr-workflow-exp` の隔離 worktree を使う。

## 4. 実装仕様

### 4.1 skill 構成

```text
.agents/skills/
  tdd-workflow/
    SKILL.md
  tdd-test-list/
    SKILL.md
  tdd-one-cycle/
    SKILL.md
  tidy-first/
    SKILL.md
  test-desiderata-review/
    SKILL.md
  tcr-workflow-exp/
    SKILL.md
```

### 4.2 spec-format template 追加項目

```markdown
### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
```

状態は `todo` / `red` / `green` / `refactor-done` / `deferred` を基本とする。種別は `new behavior` / `regression` / `edge case` / `characterization` / `hardware-gated` を基本とする。

### 4.3 skill 連携

```text
spec-format
  -> tdd-workflow
    -> tdd-test-list
    -> tdd-one-cycle
      -> tidy-first
      -> test-desiderata-review
```

実機 new 3DS XL を必要とするテスト項目は、`n3dsxl-hardware-harness` の安全条件を優先する。原典 `cc3dsfs` の値に依存するテスト項目は、`cc3dsfs-source-audit` で参照元を記録する。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| skill frontmatter | `name` と `description` が必須条件を満たす | `quick_validate.py .agents/skills/tdd-workflow` | validate が成功する |
| spec-format template | TDD 追加セクションが存在する | `Get-Content .agents/skills/spec-format/references/template.md` | 振る舞い仕様、TDD Test List、検証コマンドが確認できる |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| TDD skill 一式 validate | 追加した全 skill を検証する | skill-creator の `quick_validate.py` が利用可能 | 全 skill の validate が成功する |
| project validation | skill 追加が既存 Python 検証を壊さない | `uv` dev 環境が利用可能 | `ruff check` が成功する |

## 6. 実装チェックリスト

- [x] 本仕様書を作成する。
- [x] `spec-format` の template と説明を TDD 接続向けに更新する。
- [x] `tdd-workflow` skill を作成する。
- [x] `tdd-test-list` skill を作成する。
- [x] `tdd-one-cycle` skill を作成する。
- [x] `tidy-first` skill を作成する。
- [x] `test-desiderata-review` skill を作成する。
- [x] `tcr-workflow-exp` skill を作成する。
- [x] `AGENTS.md` の skill 一覧を更新する。
- [x] skill-creator の `quick_validate.py` で追加 skill を検証する。
- [x] `uv run ruff check .` を実行する。
- [x] レビュー完了。
