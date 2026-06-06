---
name: tdd-one-cycle
description: "TDD Test List の 1 項目だけを red/green/refactor で実行する skill。USE WHEN: 失敗するテストを 1 つ書き、最小実装で通し、必要なら green 後にリファクタリングする TDD サイクルを回すとき。"
---

# TDD One Cycle

テストリストの 1 項目だけを対象に、red、green、必要な refactor を実行する。

## Red

1. 対象項目を 1 つだけ選び、期待結果を assertion として先に明確にする。
2. 具体的で自動実行できる pytest を 1 つ追加する。
3. 最小範囲の pytest を実行し、期待した理由で失敗することを確認する。

```console
uv run pytest tests/unit -q
```

失敗理由が import error、collection error、環境不備の場合は、TDD の red として扱わず先に環境問題を直す。

## Green

1. 今のテストと既存の関連テストを通すための最小実装を行う。
2. 途中で別の振る舞いに気づいたら、実装へ混ぜず TDD Test List に追加する。
3. 対象テストと関連テストを実行し、green を確認する。

```console
uv run pytest tests/unit -q
```

型や public API を触った場合は追加で実行する。

```console
uv run ty check --no-progress
uv run ruff check .
```

## Refactor

1. green の後だけ実行する。
2. behavior change と structure change を分ける必要がある場合は `tidy-first` を使う。
3. refactor 後は同じテストを再実行し、必要なら lint / type check も実行する。

## Hardware-Gated Items

実機 new 3DS XL が必要な項目は、`n3dsxl-hardware-harness` を使う。`PONKAN_RUN_N3DSXL` や marker 条件を満たさない状態で実機 command を送らない。

## Status Update

仕様書または作業メモに、対象項目の状態を `red`、`green`、`refactor-done`、`deferred` のいずれかで反映する。
