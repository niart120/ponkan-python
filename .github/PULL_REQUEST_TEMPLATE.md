## Summary

<!-- 変更内容を1-3行で要約する。背景や動機は Related セクションのリンク先に委ねる -->

## Related

<!-- 関連する Issue・spec・原典参照・プロンプト等へのリンク。エージェント作業の場合は指示元を必ず記載する -->

- closes #
- spec:
- cc3dsfs reference:

## Changes

<!-- 論理的な変更単位でリスト化する。diff を見れば分かるファイル名の羅列ではなく「何をどう変えたか」を書く -->

-

## Commit Log

<!-- squash マージで個別コミットが消えるため、ここにコミット履歴を残す。
     `git log --oneline main..HEAD` の出力を貼り付ける。
     各コミットメッセージが変更の "Why" を記録する役割を持つ -->

```
<git log --oneline main..HEAD の出力>
```

## Testing

<!-- 実行した検証コマンドとその結果を記載する -->

```
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

## Agentic SDD Gates

<!-- Agentic SDD で作業した場合は、Work Unit と gate 結果を記載する。該当しない場合は "not used" と明記する -->

- Work Unit:
- Intent Delta:
- Non-goals:

| gate | result | evidence |
| ---- | ------ | -------- |
| Requirements |  |  |
| Plan / Tasks |  |  |
| Source Audit |  |  |
| Tests |  |  |
| Static |  |  |
| Hardware |  |  |
| Integration Review |  |  |

Subagent review:

- used / not used:
- findings and disposition:

## Hardware

<!-- 実機を使っていない場合は "not tested with hardware" と明記する -->

- [ ] not tested with hardware
- [ ] tested with N3DSXL hardware
- product string:
- VID/PID:

## Checklist

- [ ] lint / format チェック通過
- [ ] 型チェック通過
- [ ] unit test 通過
- [ ] コミット prefix (feat/fix 等) が変更の動機と一致している
- [ ] 新規・変更コードに対するテスト追加（該当する場合）
- [ ] `requires_n3dsxl` marker が必要な実機テストに付いている
- [ ] 未知 device に N3DSXL command を送らない guard を維持している

## Review Notes

<!-- レビュアーに判断を委ねたい箇所、既知のリスク、検討した代替案などを記載する。特になければセクションごと削除して良い -->

<!-- 任意セクション: 必要に応じて以下を追加する
### Screenshots
### Migration / Breaking Changes
-->
