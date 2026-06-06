# Quality Gates and Review 仕様書

更新日: 2026-06-07

## 1. 目的

Agentic SDD における review を、自律実装の主役ではなく品質ゲートとして定義する。人間は全成果物を読むのではなく、Agent が通した gate、失敗した gate、未解決リスク、高リスク差分を中心に確認する。

## 2. Gate 階層

| Gate | 実行タイミング | 主担当 | 失敗時の戻り先 |
| ---- | -------------- | ------ | -------------- |
| Git Context Gate | 変更前 | Main Agent | Branch setup / User clarification |
| Requirements Gate | Plan 前 | Main Agent | Spec / Clarify |
| Plan Gate | Tasks 前 | Main Agent | Plan |
| Source Audit Gate | 原典値使用前 | Main Agent + Subagent | Source audit |
| TDD Gate | 実装中 | Main Agent | Test / Implement |
| Static Gate | 実装後 | Main Agent / Git hooks | Implement |
| Hardware Gate | 実機 command 前 | 人間 + Main Agent | Risk Approval |
| Integration Review Gate | PR 前 | Main Agent + Subagent | Plan / Implement |

## 3. 自己レビュー報告

自己レビュー報告は、実装完了を宣言するためではなく、どの gate が通ったかを人間が確認するための圧縮成果物である。

```markdown
## Agentic SDD Report

### Work Unit
- selected:
- git context:
- intent delta:
- non-goals:

### Gates
| gate | result | evidence |
| ---- | ------ | -------- |

### Implementation
- changed behavior:
- changed structure:
- deferred:

### Source / Hardware
- cc3dsfs evidence:
- hardware used:
- hardware approval:

### Agent Review
| viewpoint | finding | disposition |
| -------- | ------- | ----------- |

### Next
- next work unit:
- open risks:
```

## 4. 人間レビュー対象

保守的運用では PR 差分レビューを残す。ただし確認優先度は次の順にする。

1. 実機 Gate と安全制約。
2. Source Audit Gate の根拠不足。
3. 失敗または未実行の deterministic check。
4. Intent Delta による scope 変更。
5. Subagent 指摘の未対応理由。
6. 通常 diff。

## 5. 実機 Gate

実機 command 前に Main Agent は次を提示し、人間承認を待つ。

Hardware phase は Main Agent が扱う。Subagent は VID/PID/product string guard、pytest marker、shutdown invariant を確認できるが、実機 command、環境変数設定、USB device 操作は実行しない。Main Agent は実機 command の承認を求める前に、並行中の Subagent 作業がないことを確認する。

| 項目 | 必須内容 |
| ---- | -------- |
| device identity | VID、PID、product string |
| command scope | pytest marker または tool |
| safety reason | 未知 device に command を送らない根拠 |
| artifact | raw `.bin` / `.json` / stats の保存先 |
| cleanup | cancel、drain、interface release、handle close の確認方法 |
| subagent state | 実機前に起動済み Subagent が完了または停止していること |

対象 command 例:

```text
uv run pytest -m requires_n3dsxl ...
uv run pytest -m "requires_n3dsxl and performance" ...
uv run python -m py3dscapture.tools.capture_raw ...
uv run python -m py3dscapture.tools.stream_n3dsxl ...
PONKAN_RUN_N3DSXL=1
PONKAN_RUN_PERFORMANCE=1
```

## 6. Subagent Review

Subagent review は gate 補助として扱う。Agentic SDD workflow の開始後、Main Agent は必要な観点を判断して Subagent を起動してよい。

| 観点 | 見るもの |
| -------- | -------- |
| source audit | cc3dsfs 由来の値、command、構造体サイズ、sequence |
| test quality | Test Desiderata、flaky risk、behavioral assertion |
| hardware safety | marker、device guard、callback 禁止事項、shutdown |
| integration risk | scope drift、public API、検証漏れ |

Main Agent は Subagent の指摘を、対応済み、未対応、却下に分類して報告する。

Subagent を起動しなかった場合も、Main Agent は理由を gate 報告に残す。
