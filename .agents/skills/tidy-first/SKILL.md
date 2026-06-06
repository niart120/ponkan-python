---
name: tidy-first
description: "Tidy First の考え方に沿って behavior change と structure change を分離し、構造改善を先に行うか後に行うか判断する skill。USE WHEN: refactor、cleanup、設計整理、実装前の下準備、TDD の green 後の構造変更判断を行うとき。"
---

# Tidy First

振る舞い変更と構造変更を分け、構造変更をいつ行うか判断する。

## Classify

| 種別 | 判断基準 | 例 |
| ---- | -------- | -- |
| Behavior change | 外部から観測できる結果、例外、I/O、USB command sequence、public API が変わる | 新しい frame 変換、device probe の結果変更 |
| Structure change | 観測可能な振る舞いを変えず、内部の読みやすさや変更容易性だけを変える | rename、helper 抽出、定数移動、重複除去 |

`cc3dsfs` 由来の command 値や sequence を変える作業は、見た目が小さくても behavior change として扱う。

## Decision

- **tidy first**: 小さな構造変更で次の behavior change が明確に小さくなる場合。既存テストまたは characterization があること。
- **tidy after**: green 後に重複や読みにくさが明確になり、次の TDD サイクルを助ける場合。
- **tidy later**: 今の振る舞い変更に不要で、リスクや範囲が大きい場合。
- **do not tidy**: 抽象化の根拠が弱い、未検証の実機 sequence に触る、または speculative な整理である場合。

## Rules

- 構造変更は観測可能な振る舞いを変えない。
- behavior change と structure change は、差分、説明、検証を分ける。
- 大きい抽象化、責務移動、外部 API 変更は tidy ではなく設計変更として仕様化する。
- green にする途中で tidy を混ぜない。green 後、または behavior change 前の明確な準備として扱う。

## Verification

構造変更の前後で、同じ検証コマンドを実行する。

```console
uv run pytest tests/unit -q
uv run ruff check .
uv run ty check --no-progress
```
