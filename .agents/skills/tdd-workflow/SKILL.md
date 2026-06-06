---
name: tdd-workflow
description: "Kent Beck の Canon TDD を project workflow として進める orchestration skill。USE WHEN: ユーザが TDD、テストリスト、red/green/refactor、t_wada 指針、仕様から実装への TDD 進行を求めるとき。仕様書が関係する場合は spec-format と併用する。"
---

# TDD Workflow

Kent Beck の Canon TDD を、ponkan-python の仕様、テスト、実装、検証に接続する。

## Git Context

通常の TDD は隔離 worktree を要求しない。変更を伴う TDD は、Agentic SDD の Git Context Gate を通した通常 worktree の作業ブランチ上で進める。

- default branch 上で red / green / refactor を始めない。read-only 調査やユーザの明示指示がある場合だけ例外にする。
- dirty worktree では既存変更を読んで、ユーザ変更を破棄しない。
- TCR をユーザが明示した場合だけ `tcr-workflow-exp` を使い、隔離 worktree へ切り替える。

## Workflow

1. 仕様が関係する作業では `spec-format` を使い、振る舞い仕様と TDD Test List を仕様書に置く。
2. `tdd-test-list` で、期待する振る舞い、variant、edge case、既存動作の回帰リスクを列挙する。
3. テストリストから次に扱う項目を必ず 1 つだけ選ぶ。小さく、自動化でき、設計上の不確実性を減らす項目を優先する。
4. `tdd-one-cycle` で red、green、必要に応じた refactor を 1 サイクルだけ実行する。
5. green 後に構造変更が必要なら `tidy-first` で behavior change と structure change を分ける。
6. 追加・変更したテストが複数の判断を含む場合は `test-desiderata-review` で trade-off を確認する。
7. 仕様書または作業メモの TDD Test List を更新し、未完了項目があれば次の 1 項目へ進む。

## Rules

- テストリストの全項目を先に実行可能テストへ変換しない。
- テストを書く段階では主に interface design を扱い、implementation design は green 後に扱う。
- red から green への途中で見つけた新しい振る舞いは、実装へ混ぜ込まずテストリストに追加する。
- refactor は green の後に行う。green にする変更と refactor を同じ判断として混ぜない。
- `cc3dsfs` 由来の定数、USB command、構造体サイズは `cc3dsfs-source-audit` で参照元を確認する。
- 実機 new 3DS XL が必要なテスト項目は `n3dsxl-hardware-harness` の marker と安全条件を優先する。

## Output

作業中は、現在の TDD 状態を簡潔に示す。

```text
TDD status:
- list item: <対象のテスト項目>
- state: red | green | refactor | done
- command: <実行した検証コマンド>
- notes: <追加したテストリスト項目や判断>
```
