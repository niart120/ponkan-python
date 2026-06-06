---
name: pr-merge-cleanup
description: "作業ブランチを GitHub PR 経由で main/master にマージし、ローカル同期・ブランチ削除まで一括実行するワークフロースキル。USE WHEN: ユーザが「PRを出して」「マージして」「ブランチをまとめて」「mainに入れて」「PRクリーンアップ」など、作業ブランチの変更をリモートに反映したい意図を示したとき。"
---

# PR Merge Cleanup

作業ブランチの変更を GitHub PR 経由でデフォルトブランチにマージし、ローカルへの同期と不要ブランチの削除まで実行する。

## 前提条件

- GitHub リモートが設定済みであること。
- 作業ブランチで全コミットが完了していること。
- GitHub への push 権限を持つこと。
- 実機を使った変更では PR template の Hardware セクションを埋めること。

## ワークフロー

1. `git branch --show-current` で現在ブランチを確認する。
2. デフォルトブランチ上であれば中断する。
3. `git status --short` で未コミット変更がないことを確認する。
4. `git push -u origin <branch>` で push する。
5. `.github/PULL_REQUEST_TEMPLATE.md` に沿って PR 本文を作成する。
6. `gh pr create` で PR を作成する。
7. 必要な check が通ったら `gh pr merge --squash` で squash merge する。
8. デフォルトブランチへ戻り、`git pull origin <default>` で同期する。
9. local / remote の作業ブランチを削除する。

## 報告項目

- PR 番号と URL。
- merge commit SHA。
- 削除した local / remote branch。
- 実行した検証コマンド。
