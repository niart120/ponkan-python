---
name: test-desiderata-review
description: "Kent Beck の Test Desiderata に基づいてテストの価値と trade-off をレビューする skill。USE WHEN: pytest、テスト設計、characterization test、実機 gated test、TDD で追加したテストの品質や脆さを確認するとき。"
---

# Test Desiderata Review

テストを万能の点数表ではなく、目的に対する trade-off としてレビューする。

## Desiderata

主に次の性質を確認する。

| 性質 | 見ること |
| ---- | -------- |
| Isolated | 実行順や他テストの状態に依存しないか。 |
| Composable | 変動要因を分けて検証できるか。 |
| Deterministic | 同じ条件で同じ結果になるか。 |
| Fast | 開発中に繰り返し実行できる速度か。 |
| Writable | 対象コードの価値に対して書くコストが過大でないか。 |
| Readable | 失敗時に意図と期待が読み取れるか。 |
| Behavioral | 実装構造ではなく観測可能な振る舞いに反応するか。 |
| Structure-insensitive | 内部構造の整理だけで壊れないか。 |
| Automated | 人手なしで実行できるか。 |
| Specific | 失敗原因が狭く分かるか。 |
| Predictive | green なら対象が実利用に耐えるという判断に近づくか。 |
| Inspiring | 通ったときに十分な信頼を与えるか。 |

## Review Process

1. テストの目的を、new behavior、regression、edge case、characterization、hardware-gated に分類する。
2. すべての性質を最大化しようとせず、今回の目的で重要な trade-off を 2 から 4 個に絞る。
3. 実機テストでは predictive と fast / deterministic の衝突を明示する。
4. characterization test では根拠、入力 artifact、期待値の由来を確認する。
5. 実装詳細に依存する assertion は、必要性が説明できる場合だけ残す。

## Output

レビュー結果は、問題の大きい順に示す。

| 指摘 | 関連する性質 | リスク | 対応 |
| ---- | ------------ | ------ | ---- |
| 例: 実行順に依存する fixture がある | Isolated / Deterministic | flaky test | fixture を test-local にする |

問題がない場合も、残る trade-off と未検証領域を明記する。
