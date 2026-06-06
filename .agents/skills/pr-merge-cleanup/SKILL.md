---
name: pr-merge-cleanup
description: "作業ブランチを GitHub PR 経由で default branch にマージし、ローカル同期・ブランチ削除まで一括実行するワークフロースキル。USE WHEN: ユーザが「PRを出して」「マージして」「ブランチをまとめて」「mainに入れて」「PRクリーンアップ」「PR後片付け」など、作業ブランチの変更をリモートに反映したい意図を示したとき。"
---

# PR Merge Cleanup

作業ブランチの変更を GitHub PR 経由で default branch に取り込み、ローカル同期と不要ブランチ削除まで行う。
この skill は project の GitHub Flow における PR 作成、merge、default branch 同期、branch cleanup を担当する。
既定は merge commit を残す `gh pr merge --merge` とし、squash merge はユーザが明示した場合だけ使う。

## Preconditions

- GitHub リモートが設定済みであること。
- 作業ブランチで必要な commit が完了していること。
- GitHub Flow の短命な作業ブランチであり、Agentic SDD / TDD の Git Context Gate を通していること。
- `git status --short` が空であること。
- default branch 上で実行していないこと。
- GitHub への push / PR / merge 権限があること。
- 実機を使った変更では PR template の Hardware セクションと Agentic SDD Gates の Hardware 行を埋めること。

## Merge Policy

| 条件 | 方法 |
| ---- | ---- |
| 既定 | `gh pr merge --merge` で merge commit を作る。 |
| ユーザが squash を明示 | `gh pr merge --squash` を使ってよい。 |
| repo が merge commit を禁止 | 中断し、許可されている merge 方法と影響を報告する。 |
| commit 履歴に修正用 commit が多い | 勝手に squash せず、rebase / fixup / squash の選択をユーザに確認する。 |

merge commit 既定の理由:

- 個別 commit が Why を担うという project rule と整合する。
- PR template の Commit Log と実際の履歴が一致する。
- Agentic SDD の Work Unit / gate の履歴を後から追いやすい。

## Skill Coordination

PR 作成前に、変更内容に応じて次の skill の結果を PR 本文へ反映する。

| 条件 | 使う skill | PR へ残すもの |
| ---- | ---------- | -------------- |
| Agentic SDD で作業した | `agentic-self-review` | Work Unit、Intent Delta、non-goals、gate 結果、次候補。 |
| 仕様書を追加・完了移動した | `spec-format` | spec path、wip / complete 状態、チェックリスト結果。 |
| TDD で実装した | `tdd-workflow` / `tdd-one-cycle` | 対象 test item、red / green / refactor、実行 command。 |
| cc3dsfs 由来値を使った | `cc3dsfs-source-audit` | 参照元、事実 / 仮説 / 未検証事項。 |
| 実機が関係する | `n3dsxl-hardware-harness` | marker、device identity、artifact、cleanup、未実行理由。 |
| テスト設計を見直した | `test-desiderata-review` | trade-off、flaky risk、残る test gap。 |
| 後回し項目が出た | `dev-journal` | 記録した項目と path。 |

該当しない skill は起動しない。起動しなかった場合でも、高リスク領域では PR の Agentic SDD Gates または Review Notes に理由を残す。

## Workflow

1. `git branch --show-current` で現在ブランチを確認する。
2. `git remote get-url origin` と default branch を確認する。
3. default branch 上であれば中断する。
4. `git status --short` で未コミット変更がないことを確認する。
5. `git log --oneline <default>..HEAD` で PR の Commit Log を作る。
6. 変更範囲から必要な skill coordination を確認する。
7. `.github/PULL_REQUEST_TEMPLATE.md` に沿って PR 本文を作成する。
8. `git push -u origin <branch>` で push する。
9. `gh pr create` で PR を作成する。
10. `gh pr checks` または `gh pr view --json statusCheckRollup` で required check を確認する。
11. required check が通ったら `gh pr merge --merge` で merge する。
12. default branch へ戻り、`git pull origin <default>` で同期する。
13. local / remote の作業ブランチを削除する。
14. PR 番号、URL、merge commit SHA、削除した branch、実行した gate を報告する。

## Stop Conditions

- 未コミット変更がある。
- default branch 上にいる。
- PR の required check が失敗または未完了。
- mergeable state が blocked / dirty / unknown。
- 実機 command が必要だが人間承認がない。
- PR template の Hardware / Agentic SDD Gates に必須情報が不足している。
- repo 側で `--merge` が許可されていない。

## PR Body Rules

- Summary は 1 から 3 行で変更の目的を示す。
- Related には spec、issue、cc3dsfs reference、作業指示元を入れる。
- Changes は diff のファイル列挙ではなく、論理的な変更単位で書く。
- Commit Log は `git log --oneline <default>..HEAD` を貼る。
- Testing は実行した command と結果を書く。未実行の gate は理由を書く。
- Hardware は実機未使用なら `not tested with hardware` を明記する。
- Agentic SDD Gates は使っていない場合も `not used` と明記する。

## Report

最終報告には次を含める。

```text
- PR: <number> <url>
- merge method: merge commit | squash | rebase
- merge commit: <sha>
- synced default branch: <branch>
- deleted branches: local=<branch>, remote=<branch>
- gates: <commands and results>
- hardware: used | not used | not run with reason
- follow-up: <dev-journal or next Work Unit>
```
