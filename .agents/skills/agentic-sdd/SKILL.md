---
name: agentic-sdd
description: "ponkan-python の Agentic Spec-Driven Development を開始・進行する入口 skill。USE WHEN: ユーザが Agentic SDD、次の Work Unit、spec/initial からの実装、Intent Delta、Subagent auto-orchestration、仕様起点の plan/tasks/implement/gate loop を求めるとき。"
---

# Agentic SDD

`AGENTS.md`、`spec/initial/*`、作業仕様を Constitution として読み、次の Work Unit を 1つだけ選んで Plan、Tasks、実装、Gate 報告へ進める。
ユーザが毎回ドメイン背景を説明し直さず、Intent Delta と Risk Approval だけを渡せる workflow にする。

## Bootstrap

1. `AGENTS.md` と `spec/initial/*` を読む。
2. 対象の `spec/wip/local_*` または `spec/complete/local_*` がある場合は読む。
3. ユーザ入力から Intent Delta を抽出する。差分がなければ `none` とする。
4. 現在の worktree と既存テストを確認し、実装済み範囲を事実として扱う。
5. 次の Work Unit を 1つだけ選ぶ。

開始時は次を短く提示する。

```text
Agentic SDD bootstrap:
- Constitution: AGENTS.md, spec/initial/*
- Intent Delta: none | <summary>
- Selected Work Unit: <Step or TDD item>
- Non-goals: <Step outside scope>
- Gates: <commands and manual gates>
- Subagents: auto | none | <sidecar list>
```

## Work Unit Rules

| 候補 | 選択条件 |
| ---- | -------- |
| `spec/initial` Step | MVP workflow の既定順に沿う作業。 |
| 作業仕様の TDD item | Step 内の小さい振る舞いを扱う作業。 |
| Source audit item | cc3dsfs 由来の値、command、構造体サイズが未確認。 |
| Hardware-gated item | 実機 new 3DS XL が必要。 |

- 選択していない Step、device、backend、GUI、audio、recording、old DS は実装しない。
- Work Unit が大きい場合は TDD item まで分割する。
- 実機 command は、device identity と実行意図への明示承認まで実行しない。
- cc3dsfs 由来の値を使う場合は `cc3dsfs-source-audit` を使う。
- 実機 safety、marker、artifact、shutdown 条件が関係する場合は `n3dsxl-hardware-harness` を使う。

## Plan And Tasks

Plan には次を含める。

```text
- selected Work Unit
- Intent Delta
- implementation scope
- non-goals
- affected files
- hardware requirement
- verification commands
- source audit requirement
```

Task Graph は次に分類する。

| 分類 | 扱い |
| ---- | ---- |
| Blocking local task | Main Agent が実行する。 |
| Sidecar task | ユーザが Subagent 利用を許可している場合、必要に応じて起動する。 |
| Hardware task | Main Agent が人間承認後に扱う。 |

## Implementation Loop

1. TDD が適する場合は `tdd-workflow`、`tdd-test-list`、`tdd-one-cycle` を使う。
2. red の理由が期待した失敗であることを確認する。
3. 最小の green を作る。
4. green 後に必要な構造変更だけ `tidy-first` で分ける。
5. gate 失敗時は、実装を続ける前に Spec、Plan、Tasks、Source audit、Implement の戻り先を決める。

## Gate Report

Work Unit 終了時は `agentic-self-review` を使い、実行した gate、未実行 gate、source/hardware 状態、Subagent 指摘の採否、次候補を報告する。
