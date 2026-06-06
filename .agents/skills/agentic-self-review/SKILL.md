---
name: agentic-self-review
description: "Agentic SDD の Work Unit 完了前に品質ゲート結果を圧縮報告する skill。USE WHEN: 実装・仕様変更後の self-review、PR 前確認、gate 結果整理、Subagent 指摘の採否整理、未実行テストや実機未検証リスクの明示が必要なとき。"
---

# Agentic Self Review

Work Unit の完了宣言ではなく、どの gate が通り、何が未検証で、どのリスクが残っているかを人間が確認できる形に圧縮する。
証拠が弱い項目は pass にしない。

## Review Process

1. 対象 Work Unit、Intent Delta、non-goals を確認する。
2. 変更差分と仕様の明示要件を照合する。
3. 実行した command、validator、test、hook、review を evidence として記録する。
4. 未実行の gate は `not run`、対象外は `not applicable` と書く。
5. Source audit、hardware approval、Subagent review の有無を分ける。
6. 問題がある場合は重大度順に findings を先に出す。
7. 問題がない場合も、残る test gap と hardware 未検証を明記する。

## Gate Checklist

| Gate | Evidence |
| ---- | -------- |
| Requirements | 対象仕様、Work Unit、non-goals との照合。 |
| Plan | Plan と Task Graph が 1 Work Unit に収まっていること。 |
| Source Audit | cc3dsfs 由来値の参照元、または該当なし。 |
| TDD / Tests | red/green 履歴、pytest 結果、未実行理由。 |
| Static | ruff format、ruff check、ty check、hook validation。 |
| Hardware | 実機使用有無、承認有無、VID/PID/product string、artifact。 |
| Integration Review | diff、scope drift、Subagent 指摘の採否。 |

## Report Template

```markdown
## Agentic SDD Report

### Work Unit
- selected:
- intent delta:
- non-goals:

### Findings
| severity | finding | evidence | disposition |
| -------- | ------- | -------- | ----------- |

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

## Rules

- 完了を証明しない evidence を pass として扱わない。
- ドキュメントのみ変更では Python test を省略できるが、skill、hook、Python script 変更は該当 validator を実行する。
- 実機 gate は、人間承認がなければ `not run` とし、勝手に実行しない。
- Subagent を使わなかった場合も理由を残す。
