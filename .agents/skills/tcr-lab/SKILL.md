---
name: tcr-lab
description: "test && commit || revert を安全な実験として扱う補助 skill。USE WHEN: ユーザが明示的に TCR、test && commit || revert、小さい increment の実験を求めるとき。通常の TDD workflow では使わない。"
---

# TCR Lab

TCR は通常の TDD 手順ではなく、明示的な実験として扱う。

## Preconditions

- ユーザが TCR を明示的に要求している。
- 一時 branch または一時 worktree で作業している。
- 作業開始時点の git 状態と戻し方を説明できる。
- 実行するテストコマンドが小さく、短時間で終わる。
- `git reset --hard`、`git clean`、`git checkout --` などの破壊的 git 操作は、project policy と明示承認がない限り実行しない。

## Safer Workflow

1. まず通常の `tdd-test-list` で小さい項目に分割する。
2. 1 increment の目標を、テスト追加、より本物の実装、変更しやすくする構造改善のいずれかに限定する。
3. テストが通ったら、ユーザが commit を求めた場合だけ commit する。
4. テストが失敗したら、破壊的 revert を自動実行せず、失敗内容と最小化案を提示する。

## Notes

Codex project policy は破壊的 git 操作を guardrail で制限している。TCR の学習価値は小さい increment と即時フィードバックにあるため、この skill では自動 revert よりも安全な一時環境と明示判断を優先する。
