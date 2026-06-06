# ponkan-python Agent Guide

ユーザとの対話は日本語で行うこと。

## 概要

`ponkan-python` は、`cc3dsfs` を参照しながら new 3DS XL capture board から USB 経由で映像フレームを取得する Python ライブラリです。

このプロジェクトは `cc3dsfs` 全体の互換移植ではありません。初期対象は new 3DS XL の映像取得、raw frame 保存、RGB8 ndarray 変換、async streaming MVP です。GUI、音声再生、録画、old DS、Optimize/Nisetro/IS 系 device は初期対象外です。

参照元:

- https://github.com/Lorenzooone/cc3dsfs
- `spec/initial/cc3dsfs_python_rebuild_spec.md`
- `spec/initial/cc3dsfs_python_n3dsxl_implementation_workflow.md`

## Agent Skills

agent skill は `.agents/skills` を正本として管理します。`.github/skills` には重複配置しません。Windows 環境を想定し、symlink 前提の配置は使いません。

主な skill:

- `agentic-sdd`: `spec/initial` と作業仕様から次の Work Unit を選び、Plan / Tasks / Implement / Gate を進める
- `agentic-self-review`: Agentic SDD の Work Unit 完了前に gate 結果、未検証リスク、次候補を圧縮報告する
- `spec-format`: 仕様書を `spec/wip/local_{連番}` または `spec/complete/local_{連番}` に作成・更新する
- `dev-journal`: 実装中の観測・疑問・先送り事項を `spec/dev-journal.md` に記録する
- `cc3dsfs-source-audit`: 原典 C++ から抽出した定数・command・構造体サイズ・仮説を記録する
- `n3dsxl-hardware-harness`: 実機 new 3DS XL capture board を使う検証の安全手順を確認する
- `tdd-workflow`: Canon TDD のテストリストから red/green/refactor までを進行する
- `tdd-test-list`: 振る舞いベースの TDD Test List を作成・更新する
- `tdd-one-cycle`: TDD Test List の 1 項目だけを red/green/refactor で実行する
- `tidy-first`: 振る舞い変更と構造変更を分け、構造改善のタイミングを判断する
- `test-desiderata-review`: Test Desiderata に基づいてテスト品質の trade-off を確認する
- `tcr-workflow-exp`: TCR を隔離 worktree 上の明示的な実験 workflow として扱う

## プロジェクト構造

```text
src/py3dscapture/
  __init__.py
  py.typed
  protocol/
    sizes.py      - capture size / USB identity constants
tests/
  unit/           - 単体テスト
  e2e/            - 実機 new 3DS XL が必要なテスト
  performance/    - 実機 streaming 性能 smoke test
spec/
  initial/        - 初期構想・MVP workflow
  wip/            - 作業中仕様
  complete/       - 完了済み仕様
.agents/skills/  - agent skill の正本
```

## Agentic SDD

`AGENTS.md`、`spec/initial/*`、作業仕様を Constitution とし、Main Agent は Intent Delta が明示された場合だけ既存仕様との差分として扱います。

ユーザが `Agentic SDD で進めて`、`次の Work Unit を進めて`、または同等の依頼をした場合、Main Agent は次を行います。

1. 現在の worktree と仕様を確認する。
2. `spec/initial` の Step、作業仕様の TDD item、source audit item、hardware-gated item から Work Unit を 1つだけ選ぶ。
3. 選択した Work Unit の対象、非対象、影響範囲、実機要否、検証 command を Plan として示す。
4. Task Graph を blocking local task、sidecar task、hardware task に分ける。
5. ユーザが Subagent 利用を許可している場合、sidecar task や観点別 gate に必要な Subagent を起動し、結果の採否を Main Agent が統合する。
6. TDD が適する実装では 1項目ずつ red / green / refactor を進める。
7. Work Unit 終了時に gate 結果、未実行 gate、source / hardware 状態、次候補を報告する。

未選択の Step、device、backend、GUI、audio、recording、old DS は実装しません。
実機 command は、device identity、command scope、安全理由、artifact、cleanup の説明と人間の明示承認があるまで実行しません。

## 実機安全制約

- product string が `N3DSXL` / `N3DSXL.2` でない device に N3DSXL command を送らない。
- VID/PID が仕様で許可された値に一致しない device に N3DSXL command を送らない。
- 実機テストには `@pytest.mark.requires_n3dsxl` を付ける。
- performance test には `@pytest.mark.performance` も付ける。
- CI で実機テストを実行しない。
- USB command 値、構造体サイズ、sequence は原典 `cc3dsfs` の参照箇所を記録する。
- callback 内で decode、Pillow 変換、blocking queue put、同期 libusb API 呼び出しを行わない。
- streaming は bounded queue と明示的な drop policy を持つ。
- shutdown では pending transfer cancel、drain、interface release、handle close を行う。

## Python

- Python `>=3.12, <3.14` を使います。現在の基準は `.python-version` の Python 3.13 です。
- パッケージ管理と Python 実行は `uv` 経由に統一します。
- Python スクリプトは `python ...` ではなく `uv run python ...` で実行します。
- 依存追加は `uv add <pkg>`、dev 依存は `uv add --dev <pkg>` を使います。
- 型注釈は Python 3.12+ の構文を使います。
  - `X | None`
  - `list[X]` / `dict[K, V]`
  - `tuple[int, str]`
- `from __future__ import annotations` は、実行時評価を遅延する必要がある場合だけ使います。
- ランタイムに不要な型 import は `if TYPE_CHECKING:` に置きます。

## コーディング規約と設計方針

- 技術文書は事実ベース・簡潔に記述します。
- t_wada 氏の TDD 指針を意識します。
- Code は How、Tests は What、Commits は Why、Comments は Why not を担います。
- コメントは、コードだけでは読み取りにくい判断理由がある場合に限って追加します。
- 副作用のないロジック関数は実機なしで単体テスト可能にします。
- 原典 C++ の移植判断では、事実・仮説・未検証事項を分けて記録します。

## テストと検証

- lint / format は `ruff`、型チェックは `ty`、テストは `pytest` を使います。
- 実機要件のテストには `@pytest.mark.requires_n3dsxl` を指定します。
- 実機 performance test には `@pytest.mark.performance` を追加します。
- 変更範囲に応じて、ruff、ty、pytest を実行します。

```console
uv sync --dev
scripts/install-git-hooks.ps1
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

## Hooks / Codex Policy

- Git hooks は `.githooks/` を正本とし、`git config core.hooksPath .githooks` で有効化する。
- clone 後は `scripts/install-git-hooks.ps1` または `sh scripts/install-git-hooks.sh` を実行する。
- Codex project-local hooks / rules は `.codex/` に置く。
- 生 `python` / `pip` / `pytest` / `ruff` / `ty` は使わず、`uv run ...` または `uv add ...` を使う。
- project `.codex/` layer は trusted project でだけ読み込まれる。hook 変更後は `/hooks` で review/trust する。
- 実機 command は `.codex` hook で承認フラグなしの実行を block する。人間承認後に限り、同じ command 内で `PONKAN_HARDWARE_APPROVED=1` を明示する。

実機テスト:

```console
$env:PONKAN_RUN_N3DSXL = "1"
uv run pytest -m requires_n3dsxl tests/e2e

$env:PONKAN_RUN_PERFORMANCE = "1"
uv run pytest -m "requires_n3dsxl and performance" tests/performance
```

## コミットルール

Conventional Commits に準拠します。

```text
<type>(<scope>): <subject>
```

`scope` は省略可です。type は `feat` / `fix` / `docs` / `style` / `refactor` / `perf` / `test` / `build` / `ci` / `chore` / `revert` を使います。subject は日本語で記述し、末尾句点は付けません。
