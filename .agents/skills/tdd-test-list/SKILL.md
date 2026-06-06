---
name: tdd-test-list
description: "Canon TDD の最初の分析段階として、振る舞いベースのテストリストを作成・更新する skill。USE WHEN: テストシナリオ、TDD Test List、期待する振る舞い、edge case、回帰確認項目を仕様や実装前に洗い出すとき。"
---

# TDD Test List

実装設計ではなく、観測可能な振る舞いの分析としてテストリストを作る。

## Inputs

- ユーザの要求、issue、既存仕様書。
- `spec-format` の `振る舞い仕様` と `TDD Test List`。
- `cc3dsfs` 原典に依存する場合は、参照元と未検証仮説。
- 実機 new 3DS XL に依存する場合は、実機 gated であること。

## Process

1. 新しい振る舞い、既存振る舞いの維持、edge case、error handling、characterization を分けて列挙する。
2. 各項目に、入力・状態、期待結果、検証レイヤー、実機要否を付ける。
3. 実装方法、内部構造、抽象化案はテスト項目に混ぜない。必要なら設計メモとして分離する。
4. 不確実な値や `cc3dsfs` 由来の値は、確定値ではなく仮説として記録する。
5. 次に実行する 1 項目を選ぶ。小さく、自動化でき、失敗理由が明確になる項目を優先する。

## List Format

仕様書に書く場合は次の形を使う。

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | 期待する振る舞いを 1 つだけ書く | new behavior | 3.1 | 入力、期待結果、実機要否を書く |

状態は `todo` / `red` / `green` / `refactor-done` / `deferred` を使う。種別は `new behavior` / `regression` / `edge case` / `characterization` / `hardware-gated` を基本にする。

## Quality Gate

- 各項目は assertion に変換できる観測可能な結果を持つ。
- 1 項目が複数の独立した期待結果を含む場合は分割する。
- テストだけで検証できない実機項目は `hardware-gated` として明示する。
- 期待値を実行結果から丸写しして作る必要がある項目は、characterization として扱い根拠を記録する。
