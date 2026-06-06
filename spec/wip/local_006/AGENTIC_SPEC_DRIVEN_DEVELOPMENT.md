# Agentic Spec-Driven Development 仕様書

更新日: 2026-06-07

## 1. 概要

### 1.1 目的

`ponkan-python` の開発を、AI Agent が仕様を起点に自律的に設計・実装・検証へ進められる workflow として体系化する。

この仕様ではレビューを主役にしない。主軸は `spec/initial` と作業仕様を中心にした Spec-Driven Development であり、自己レビュー、Subagent レビュー、hooks、tests は自律実装を止めるための品質ゲートとして扱う。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| Agentic SDD | 仕様を source of truth とし、AI Agent が plan、task、implementation、verification を進める開発方式。 |
| Constitution | Agent が常に守る project-level 原則。`AGENTS.md`、`spec/initial`、安全制約を指す。 |
| Intent Delta（意図差分） | 既存仕様に対する今回の目的、優先度、制約変更。毎回ドメイン背景を説明し直すのではなく差分だけを渡す。 |
| Work Unit | Agent が一度に実装する最小作業単位。`spec/initial` の Step または TDD Test List 1項目。 |
| Task Graph | Work Unit を依存関係で並べた実装順序。独立 task は Subagent に分担する候補になる。 |
| Subagent Auto-Orchestration | ユーザが Agentic SDD workflow を開始し、Subagent 起動判断を Main Agent に委譲した後、Main Agent が必要に応じて Subagent を起動する project-local 運用。 |
| Quality Gate | 実装の前後で通す確認。requirements consistency、source audit、tests、type/lint、hardware safety など。 |
| Main Agent | ユーザと対話し、scope 切り、実装統合、検証、最終報告を担当する Agent。 |
| Subagent | Main Agent から明示的に起動され、調査、レビュー、独立 task を担当する Agent。 |

### 1.3 背景・問題

AI Agent に設計・実装・検証を委譲するには、レビュー結果だけでなく、仕様、計画、task 分解、検証を一続きの workflow として扱う必要がある。

外部の類似手法では、Spec Kit は `Spec -> Plan -> Tasks -> Implement` を中核にし、clarify、checklist、analyze を実装前ゲートとして使う。Kiro の specs も requirements、design、tasks を分け、task 依存関係に基づいて並列実行可能な単位を扱う。Agentic coding の実践では、Agent に検証可能な check を与え、探索、計画、実装、検証を loop させることが重視されている。

`ponkan-python` では、`spec/initial/cc3dsfs_python_rebuild_spec.md` と `spec/initial/cc3dsfs_python_n3dsxl_implementation_workflow.md` が既にドメインコンテキスト、MVP scope、非対象、安全制約、実装順序を多く満たしている。そのため、人間が毎回「何を作りたいか」を厚く説明し直す必要はない。必要なのは、既存仕様に対する Intent Delta と、Agent が次の Work Unit を選んで進めるための bootstrap である。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| 作業開始 | ユーザが都度まとまった意図を説明する | 既存仕様を前提に、Intent Delta だけで開始できる |
| 実装順序 | `spec/initial` の Step を人間が都度指定する | Main Agent が Step / TDD item から次の Work Unit を提案・選択する |
| 並列化 | Subagent 利用が個別判断 | Main Agent が必要に応じて sidecar task を起動し、観点別 gate を並列化する |
| 品質管理 | レビュー結果を人間が読む | Agent が gate を通し、失敗時に仕様・plan・task へ戻す |
| 実機安全 | 実機 test は個別判断 | 実機 command は毎回人間承認を必須にする |

### 1.5 着手条件

- [x] `AGENTS.md` に project constitution がある。
- [x] `spec/initial` に MVP scope、非対象、実装 Step、安全制約がある。
- [x] `.agents/skills` に spec、TDD、source audit、hardware harness、test review の skill がある。
- [x] `.codex` と `.githooks` に基本 command guardrail がある。
- [x] 初期運用は「保守的運用」「ローカル中心」「実機は毎回人間承認」とする。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_006/AGENTIC_SPEC_DRIVEN_DEVELOPMENT.md` | 新規 | Agentic SDD 全体像を定義する。 |
| `spec/wip/local_006/AGENT_BOOTSTRAP_PLAYBOOK.md` | 新規 | ユーザと Main Agent の開始手順を定義する。 |
| `spec/wip/local_006/QUALITY_GATES_AND_REVIEW.md` | 新規 | review を品質ゲートとして再定義する。 |
| `spec/wip/local_006/RESEARCH_NOTES.md` | 新規 | 調査した外部手法と採用判断を記録する。 |
| `spec/initial/cc3dsfs_python_n3dsxl_implementation_workflow.md` | 修正 | 既存 Step を Agentic SDD の Work Unit 候補として扱う方針を追記する。 |
| `AGENTS.md` | 修正 | Agentic SDD、Intent Delta、Work Unit、Subagent auto-orchestration 方針を追記する。 |
| `.agents/skills/agentic-sdd/` | 新規 | Agentic SDD の入口 skill を追加する。 |
| `.agents/skills/agentic-self-review/` | 新規 | Quality Gate 報告用 skill を追加する。 |
| `.github/PULL_REQUEST_TEMPLATE.md` | 修正 | Agentic SDD / gate 結果欄を追加する。 |
| `.codex/rules/default.rules` | 修正 | 実機系 command の事前確認ルールを追加する。 |
| `.codex/hooks/pre_tool_use_policy.py` | 修正 | 実機系 command を検出し、承認境界を明確にする。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| 既存仕様から開始する | `spec/initial` と `AGENTS.md` が存在する | Main Agent はこれを既定コンテキストとして扱い、追加説明を要求しない | 人間は差分だけ渡す |
| Intent Delta を受け取る | ユーザが目的、優先 Step、制約変更を短く渡す | Main Agent が差分を仕様または作業メモに反映する | 既存仕様で足りる場合は不要 |
| Work Unit を選ぶ | 方針が固まっている | Main Agent が次の Step または TDD Test List 1項目を選ぶ | 未選択の Step は実装しない |
| Plan を作る | Work Unit が決まる | 実装対象、非対象、影響範囲、検証コマンド、実機要否を明示する | 実装前 gate |
| Tasks へ分解する | Plan がある | 依存関係つき task list を作る | 独立 task は Subagent 候補 |
| Subagent を自動起動する | sidecar task または観点別 gate がある | Main Agent が必要に応じて Subagent を起動し、結果を統合する | Agentic SDD 開始指示を包括的許可として扱う |
| Implement する | Tasks がある | Main Agent が TDD で小さく実装する | Subagent の成果は Main Agent が統合する |
| Gate を通す | 実装または仕様変更がある | tests、lint/type、source audit、hardware safety、self-review を通す | gate 失敗時は戻る |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | `agentic-sdd` skill が Spec -> Plan -> Tasks -> Implement を案内する | new behavior | 3.1 | 入口 skill |
| todo | Intent Delta だけで bootstrap できる prompt を `AGENTS.md` に追加する | new behavior | 3.1 | 毎回の厚い説明を避ける |
| todo | Work Unit 選択時に未選択 Step を実装しない rule を明記する | regression | 3.1 | 既存 workflow と整合 |
| todo | task graph で Subagent 分担可否を判定し、必要に応じて sidecar task を起動する | new behavior | 3.1 | 過度な分担は避ける |
| todo | gate 失敗時に spec / plan / task へ戻る loop を定義する | new behavior | 3.1 | review 偏重を避ける |

### 3.3 設計方針

この repo の Agentic SDD は、外部 tool の Spec Kit をそのまま導入しない。既存の `spec/initial`、`.agents/skills`、`.codex`、`.githooks` を活かし、軽量な project-local workflow として実装する。

Subagent は採用する。Codex 製品としては subagent 起動に明示依頼が必要だが、この repo ではユーザが「Agentic SDD で進めて」「次の Work Unit を進めて。必要に応じて Subagent を起動してよい」と依頼した時点で、Main Agent に Subagent auto-orchestration を委譲したものとして扱う。

基本 loop:

```text
Constitution
  AGENTS.md
  spec/initial/*
  .agents/skills/*
      ↓
Intent Delta
  今回だけの目的・優先度・制約変更
      ↓
Spec / Clarify
  既存仕様で足りるか、作業仕様が必要かを判断
      ↓
Plan
  Work Unit、非対象、影響範囲、実機要否、検証を決める
      ↓
Tasks
  依存関係つき task graph を作る
      ↓
Subagent Sidecars
  調査・観点別 gate を並列化する
      ↓
Implement
  TDD で 1項目ずつ進める
      ↓
Quality Gates
  tests / lint / type / source audit / hardware gate / self-review
      ↓
Integrate
  PR notes、dev-journal、次の Work Unit
```

人間の関与は次の 3点に絞る。

| 関与点 | 役割 | 既定 |
| ------ | ---- | ---- |
| Intent Delta | 既存仕様から変えることだけ渡す | 省略可 |
| Risk Approval | 実機、安全、scope 拡張、公開 API 変更を承認する | 必須 |
| Review Sampling | gate 報告と高リスク差分を見る | 保守的に PR review も維持 |

## 4. 実装仕様

### 4.1 Work Unit 選択規則

Main Agent は、実装開始前に次を 1つだけ選ぶ。

| 候補 | 選択条件 | 例 |
| ---- | -------- | -- |
| `spec/initial` Step | MVP の既定順序に沿う作業 | Step 1 device listing |
| 作業仕様の TDD item | 既存 Step 内の小さな振る舞い | product string 不一致 device を候補にしない |
| Source audit item | 原典値が未確定 | FTD3 command payload の由来確認 |
| Hardware-gated item | 実機が必要 | open / claim / close E2E |

選択しなかった Step、device、backend、GUI、audio、recording、old DS は実装しない。

### 4.2 Subagent Auto-Orchestration

Main Agent は、Agentic SDD workflow の開始後、次に該当する場合はユーザへ追加確認せず Subagent を起動する。

| Trigger | Subagent に期待する観点 |
| ------- | ----------------------- |
| cc3dsfs 由来の値、command、構造体サイズ、sequence がある | 原典根拠と未検証仮説 |
| 新規または変更 test が複数判断を含む | テスト品質と trade-off |
| 実機 command、pytest marker、USB device guard が絡む | 実機安全と marker 条件 |
| Work Unit が複数 file / layer にまたがる | 統合リスクと scope drift |
| 仕様、plan、tasks の整合性に不安がある | 仕様・計画・task の一貫性 |

Subagent 起動は、Main Agent が Work Unit の性質と統合コストを見て判断する。起動した Subagent は、担当観点の結果を Main Agent に返し、Main Agent が統合判断を行う。

### 4.3 Task Graph

Plan 後、Main Agent は task を次の分類へ分ける。

| 分類 | 扱い | 理由 |
| ---- | ---- | ---- |
| Blocking local task | Main Agent が扱う | 次の実装判断に直結する |
| Sidecar task | Subagent 候補 | 原典確認、テスト観点、既存 pattern 調査などを並行できる |
| 並列実装候補 | 後段で検討 | 変更範囲と統合リスクが明確に説明できる場合に扱う |
| Hardware task | Main Agent が扱う | 人間承認と実機状態が必要 |

### 4.4 Gate Loop

gate 失敗時は、実装を続ける前に戻り先を決める。

| 失敗 | 戻り先 |
| ---- | ------ |
| requirement ambiguity | Spec / Clarify |
| plan/task inconsistency | Plan / Tasks |
| source evidence missing | Source audit |
| red が期待理由でない | Environment / Test setup |
| unit test failure | Implement |
| type/lint failure | Implement または Tidy First |
| hardware identity missing | Risk Approval |
|実機結果が仕様と矛盾 | Spec / dev-journal |

### 4.5 成果物

Agentic SDD の各 Work Unit は、最低限次を残す。

```text
- selected Work Unit
- Intent Delta の有無
- 実装したこと / しなかったこと
- 実行した gate と結果
- 原典 audit の有無
- 実機 gate の状態
- 起動した Subagent とその採否
- 次の Work Unit 候補
```

自己レビュー報告はこの一部であり、最終目的ではない。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| `agentic-sdd` skill | frontmatter と workflow 記述が valid | `quick_validate.py .agents/skills/agentic-sdd` | validate が成功する |
| bootstrap prompt | Intent Delta なしで既存仕様から開始できる | `次の Work Unit を進めて` | Main Agent が repo 探索後に候補を出す |
| task graph | sidecar task と blocking task を分ける | Step 3 FTD3 command pipe | 原典調査 Subagent が自動起動候補になる |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| Work Unit 実装 | 1項目だけ TDD で進む | unit-testable item | 対象 test が red -> green になる |
| Source audit gate | 原典値を使う実装 | cc3dsfs 参照が必要 | 参照元 path / URL が残る |
| Hardware gate | 実機 command が必要 | requires_n3dsxl item | 人間承認前に停止する |

### 検証コマンド

```console
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

ドキュメントのみの変更では Python 検証を省略できる。skill、hook、Python script を変更した場合は該当検証を実行する。

## 6. 実装チェックリスト

- [x] 既存の自己レビュー中心仕様を Agentic SDD 中心へ再構成する。
- [x] 外部の Spec-Driven Development / Agentic Coding 事例を調査し、採用判断を記録する。
- [x] `spec/initial/cc3dsfs_python_n3dsxl_implementation_workflow.md` に Work Unit と bootstrap 方針を反映する。
- [ ] `agentic-sdd` skill を追加する。
- [ ] `agentic-self-review` skill を Quality Gate 報告用として追加する。
- [ ] `AGENTS.md` に Intent Delta、Work Unit bootstrap、Subagent auto-orchestration を追記する。
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` に Agentic SDD gate 結果欄を追加する。
- [ ] `.codex` rules / hook に実機系 command の承認境界を追加する。
- [ ] skill と hook の検証を実行する。
- [ ] レビュー完了。
