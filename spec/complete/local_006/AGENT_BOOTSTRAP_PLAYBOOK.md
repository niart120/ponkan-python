# Agent Bootstrap Playbook

更新日: 2026-06-07

## 1. 目的

ユーザが複数 Agent 群に作業を始めさせるときの入口を定義する。`ponkan-python` では `spec/initial` が既に十分なドメインコンテキストを持つため、ユーザは原則として差分だけを渡す。

## 2. ユーザの立ち位置

ユーザは Agent 群の直接 manager ではなく、project intent と risk approval の owner として振る舞う。

| タイミング | ユーザが渡すもの | 省略可否 |
| ---------- | ---------------- | -------- |
| 開始時 | 今回の Intent Delta（意図差分） | 省略可 |
| scope 変更時 | 既存仕様から外れる理由 | 必須 |
| 実機前 | device identity と実行意図の承認 | 必須 |
| 終了時 | gate 報告と高リスク差分の確認 | 保守的運用では実施 |

Intent Delta がない場合、Main Agent は `AGENTS.md` と `spec/initial` の範囲で次の Work Unit を選ぶ。

## 3. Main Agent の立ち位置

Main Agent は、ユーザから曖昧な作業依頼を受けても、すぐ Subagent 群へ丸投げしない。まずローカルで repo 事実を確認し、Work Unit を 1つに切る。

Main Agent の責務:

1. `AGENTS.md` と `spec/initial` を既定コンテキストとして読む。
2. 変更を伴う作業では branch、default branch、dirty 状態を確認する。
3. Intent Delta がある場合だけ、既存仕様との差分として扱う。
4. 次の Work Unit を 1つ選ぶ。
5. Plan と Task Graph を作る。
6. Subagent に出す sidecar task を切り出す。
7. sidecar task や観点別 gate がある場合は、必要に応じて Subagent を起動する。
8. blocking task と実装統合を担当する。
9. Gate 結果と次の Work Unit 候補を報告する。

## 3.1 Git Context

変更を伴う Work Unit では、Main Agent は作業開始前に `git branch --show-current` と `git status --short` を確認する。default branch 上で clean な場合は、read-only 調査やユーザの明示指示を除き、作業ブランチを作るか既存作業ブランチへ切り替える。dirty worktree では既存変更を読んで、ユーザ変更を破棄しない。

TCR をユーザが明示した場合だけ `tcr-workflow-exp` の隔離 worktree を使う。通常の TDD / Agentic SDD は通常 worktree 上の作業ブランチで進める。

## 4. Bootstrap 入力

### 4.1 最小形

```text
次の Work Unit を Agentic SDD で進めて。
必要に応じて Subagent を起動してよい。
実機 command は明示承認まで実行しない。
```

この場合、Main Agent は `spec/initial` の Step と現状実装を確認し、次に進めるべき Work Unit を提案または選択する。

### 4.2 推奨形

```text
Agentic SDD で進めて。
対象: spec/initial Step <番号または名前>
Intent Delta: <既存仕様から今回だけ変えたいこと。なければ「なし」>
実機利用: なし / 要相談 / 明示承認後のみ
```

### 4.3 高リスク形

```text
Agentic SDD で進めて。
対象: <spec path または Step>
Intent Delta: <scope 変更、API 変更、実機を伴う理由>
Risk Approval が必要な点: <人間判断したい点>
```

## 5. Subagent 起動規則

Subagent は、Main Agent が task graph を切った後に使う。ユーザが Agentic SDD workflow を開始した場合、sidecar task の起動は Main Agent に委譲されたものとして扱う。

| 使う場面 | Subagent に期待する観点 | 例 |
| -------- | ----------------------- | -- |
| 原典調査が実装と並行できる | source audit | cc3dsfs の command 値確認 |
| test design を独立確認できる | test quality | Test Desiderata 観点 |
| scope drift を確認したい | integration risk | Step 外実装の検出 |
| hardware safety を実行前に確認したい | hardware safety | marker、VID/PID/product string guard |
| spec / plan / tasks の整合性を見たい | spec consistency | 実装前 analyze |

Subagent に渡す task は、次を含める。

```text
- 対象 Work Unit
- 読むべき仕様 / ファイル
- 禁止事項
- 出力形式
- 作業範囲
```

Subagent の使い方は Work Unit の性質に合わせて Main Agent が判断する。起動した Subagent は結果を Main Agent に返し、Main Agent が統合判断を行う。

## 6. Bootstrap 後の標準出力

Main Agent は開始直後に次を出す。

```text
Agentic SDD bootstrap:
- Constitution: AGENTS.md, spec/initial/*
- Git Context: <branch>, <clean | dirty>, <normal branch | isolated worktree | read-only>
- Intent Delta: none | <summary>
- Selected Work Unit: <Step or TDD item>
- Non-goals: <Step outside scope>
- Gates: <commands and manual gates>
- Subagents: auto | none | <sidecar list>
```

この出力が、ユーザにとっての entry point 確認になる。
