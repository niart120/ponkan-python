# PyPI Release Operations 仕様書

## 1. 概要

### 1.1 目的

`ponkan-python` の PyPI リリース手順を、一般的な Python packaging / PyPI Trusted Publishing の流れと照合しながら、再実行可能な project-local 運用として整備する。次回以降のバージョンアップ時に、`pypi-release` skill が release preflight、version bump、PR merge、tag publish、post-publish smoke check を一貫して案内できる状態にする。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| distribution name | PyPI 上の配布名。現行は `ponkan-python`。 |
| import package | 利用者が `import` する Python package 名。現行は `ponkan`。 |
| sdist | source distribution。PyPI に upload する source archive。 |
| wheel | built distribution。Pure Python package では通常 `py3-none-any.whl` を生成する。 |
| Trusted Publishing | PyPI API token ではなく GitHub Actions OIDC identity で PyPI へ publish する方式。 |
| TestPyPI | PyPI 本番とは別の検証用 package index。 |
| release preflight | tag を作る前に行う metadata、version、build、CI、docs、smoke plan の確認。 |
| release PR | release version bump と release docs / notes の準備を行う PR。 |
| release tag | PyPI production publish を起動する `vX.Y.Z` tag。 |
| version-specific endpoint | `https://pypi.org/pypi/ponkan-python/X.Y.Z/json` のように特定 version を確認する PyPI JSON API。 |

### 1.3 背景・問題

現行 repo は `pyproject.toml`、Hatchling、`uv build`、GitHub Actions Trusted Publishing を使っており、PyPI publish の基本構造は一般的な Python packaging flow に沿っている。`.github/workflows/publish.yml` も build job と publish job を分け、artifact 経由で同一 dist を publish しているため、PyPA の推奨に近い。

一方で、運用手順としては次の弱点が残っている。

| 問題 | 現状 | 影響 |
| ---- | ---- | ---- |
| docs drift | `docs/publishing.md` の Python support が `pyproject.toml` とずれている | release 前の metadata 判断を誤る |
| local gate 不足 | `docs/publishing.md` の local release check に `uv lock --check` と `twine check` がない | lock drift、README / metadata rendering 破損を見落とす |
| version policy 未固定 | patch / minor / major の判断規則が skill 化されていない | release version の判断が都度属人化する |
| release note 方針未固定 | PyPI publish 後に GitHub Release / changelog をどう扱うか未定義 | 利用者向け変更説明が不足しやすい |
| smoke check pin 不足 | docs の例が version pin なし | 新規 release ではなく latest / cache を確認する恐れがある |
| tag 操作の停止条件不足 | PyPI 既存 version、tag 重複、dirty default branch の扱いが docs に弱い | 不可逆な publish 操作の事故につながる |
| skill 未整備 | PyPI release 用 skill がない | 毎回過去メモと docs を再構成する必要がある |

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| release 手順の再現性 | 過去メモと `docs/publishing.md` を都度参照 | `.agents/skills/pypi-release` と docs で一貫した手順になる |
| 一般 Python release との整合 | 大枠は整合しているが docs 上の根拠が薄い | Python Packaging / PyPI / PyPA action の推奨点を release preflight に反映する |
| metadata drift 検出 | 手動 grep 依存 | `pyproject.toml`、`uv.lock`、`docs/publishing.md` の整合 check を必須化する |
| publish 前検証 | ruff / ty / pytest / build が中心 | `uv lock --check`、`uv build`、`twine check`、wheel content smoke を含める |
| publish 後検証 | version pin なし smoke 例が残る | `ponkan-python==X.Y.Z` と version-specific PyPI JSON で確認する |
| irreversible 操作の安全性 | tag push 手順のみ記載 | tag 作成前の stop conditions と人間承認境界を明確化する |

### 1.5 着手条件

- [x] `master` が clean であることを確認した。
- [x] 作業ブランチ `docs/pypi-release-operations-spec` を作成した。
- [x] 現行 `docs/publishing.md` と `.github/workflows/publish.yml` を確認した。
- [x] Python Packaging User Guide、PyPI Trusted Publishers docs、`pypa/gh-action-pypi-publish` docs の該当方針を確認した。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_026/PYPI_RELEASE_OPERATIONS.md` | 新規 | 本仕様を追加する。 |
| `.agents/skills/pypi-release/SKILL.md` | 新規予定 | PyPI release の preflight / version bump / publish / smoke workflow を skill 化する。 |
| `.agents/skills/pypi-release/agents/openai.yaml` | 新規予定 | skill UI metadata を追加する。 |
| `docs/publishing.md` | 修正予定 | release preflight、TestPyPI、本番 publish、GitHub Release / smoke check、stop conditions を更新する。 |
| `AGENTS.md` | 修正予定 | 主要 skill 一覧に `pypi-release` を追加する。 |
| `.github/workflows/publish.yml` | 修正なし予定 | 現行の tag-driven Trusted Publishing workflow は維持する。必要な改善が見つかった場合のみ別 Work Unit とする。 |
| `pyproject.toml` | 修正なし予定 | release version bump は実際の release Work Unit で行う。本仕様整備では変更しない。 |
| `uv.lock` | 修正なし予定 | release version bump は実際の release Work Unit で行う。本仕様整備では変更しない。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| release preflight を開始する | ユーザが PyPI release、バージョンアップ、deploy、publish を依頼 | `pypi-release` skill が現在 branch、dirty state、default branch、latest tag、PyPI 既存 version を確認する | tag 作成前に必ず行う |
| 一般 Python release との整合を確認する | release docs / workflow を読む | `pyproject.toml` metadata、sdist/wheel build、Trusted Publishing、post-publish install smoke が揃っているか報告する | docs drift は stop condition |
| release type を判断する | latest tag 以降の commit と user intent | `patch` / `minor` / `major` / explicit version の候補を示す | pre-alpha でも判断理由を残す |
| release PR を作る | release version が決まった | `release/vX.Y.Z` branch で `pyproject.toml`、`uv.lock`、release docs / notes を更新し、local gates を通す | PR merge は `pr-merge-cleanup` に委譲 |
| TestPyPI を扱う | user が staging publish を求める、または publish surface が高リスク | `workflow_dispatch` の TestPyPI path を案内し、本番 PyPI とは別 gate として扱う | production publish は tag push のみ |
| production publish を行う | release PR merge 済み、clean default branch、version 未公開 | annotated `vX.Y.Z` tag を作成し push する | tag push は不可逆操作として最終確認を入れる |
| publish workflow を確認する | `Publish` workflow run が起動 | build / publish job の成功を確認し、failure は build failure と publish failure に分けて判断する | attestation / network failure は rerun 候補 |
| post-publish smoke を行う | PyPI version が表示される | version-specific JSON と `uvx --from ponkan-python==X.Y.Z` で install / CLI / optional extra を確認する | generic latest endpoint だけで判断しない |
| release note を残す | PyPI publish が成功 | GitHub Release か release report に user-facing summary、gate、known limitation を残す | 初期実装では GitHub Release 作成を推奨 gate とする |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | `pypi-release` skill frontmatter が valid | skill validation | 3.1 | `quick_validate.py .agents/skills/pypi-release` |
| todo | `docs/publishing.md` と `pyproject.toml` の Python support 表記が一致する | docs regression | 3.1 | grep または manual check |
| todo | local release check に `uv lock --check`、`uv build`、`twine check` が含まれる | docs regression | 3.1 | `docs/publishing.md` |
| todo | post-publish smoke が `==X.Y.Z` pin を使う | docs regression | 3.1 | `docs/publishing.md` |
| todo | `AGENTS.md` の skill 一覧に `pypi-release` が含まれる | docs regression | 2 | project skill discovery |
| todo | release docs から古い `>=3.12, <3.14` 表記が消える | docs regression | 1.3 | local_025 と整合 |

### 3.3 設計方針

Python release の一般手順は次の順で扱う。

1. `pyproject.toml` に package metadata と build backend を置く。
2. release version を決める。
3. sdist と wheel を build する。
4. build artifact を検査する。
5. TestPyPI が必要な場合は本番前に別 index へ publish する。
6. PyPI 本番へ publish する。
7. fresh install smoke と release note を残す。

この repo では、upload は手元の `twine upload` ではなく GitHub Actions Trusted Publishing に統一する。理由は、PyPI API token をローカルや repository secret に置かず、GitHub environment approval と OIDC identity を使えるためである。

`release-please` はこの Work Unit では導入しない。5genSearch-web の `gh-pages-release` は release-please PR を merge して tag / GitHub Release / Pages deploy を発火する workflow だが、ponkan-python は既に tag-driven publish workflow を持つ。今は release automation の責務を `pypi-release` skill と `docs/publishing.md` に置き、必要になったら別 Work Unit で release-please / changelog automation を評価する。

release PR と tag publish は分ける。version bump、docs、release note draft は PR で review 可能にする。tag push は merge 済み default branch でのみ行い、dirty worktree、未同期 default branch、既存 tag、既存 PyPI version、failed gate があれば中断する。

`pypi-release` skill は `pr-merge-cleanup` を置き換えない。release PR の作成と publish gate を担当し、PR 作成 / merge / branch cleanup は既存 `pr-merge-cleanup` に委譲する。

## 4. 実装仕様

`pypi-release` skill の frontmatter は次の方向にする。

```yaml
---
name: pypi-release
description: "ponkan-python の PyPI release を計画・実行する workflow skill。USE WHEN: ユーザが PyPI へのデプロイ、ライブラリのバージョンアップ、release tag 作成、TestPyPI / PyPI publish、post-publish smoke check、release 手順の確認を依頼したとき。"
---
```

skill body は次のセクションを持つ。

| セクション | 内容 |
| ---------- | ---- |
| Purpose | PyPI release の計画、preflight、publish、smoke を扱うことを明記する。 |
| Inputs | `version`、`releaseType`、`includeTestPyPI`、`createGitHubRelease`、`hardwareSmoke` を扱う。 |
| Preconditions | clean branch、GitHub auth、PyPI Trusted Publisher、release docs、workflow の存在を列挙する。 |
| Preflight | branch / dirty state / latest tag / PyPI JSON / metadata drift / local gates を確認する。 |
| Version Policy | patch / minor / major / explicit version の判断規則を書く。 |
| Release PR | `release/vX.Y.Z` branch、version bump、`uv lock`、docs / note update、gate を定義する。 |
| TestPyPI | `workflow_dispatch` path と production path の違いを明記する。 |
| Production Publish | annotated tag、push、workflow watch、failure classification を定義する。 |
| Post-Publish | PyPI JSON、`uvx --from ...==X.Y.Z`、optional extra smoke、GitHub Release / final report を定義する。 |
| Stop Conditions | dirty state、existing version、failed gate、pending CI、missing approval、metadata drift を列挙する。 |

`docs/publishing.md` は、少なくとも次の内容に更新する。

```console
uv sync --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
uv build
uvx --from twine twine check dist\*
```

post-publish smoke は release version を pin する。

```console
uvx --from ponkan-python==X.Y.Z python -c "import importlib.metadata, ponkan; print(importlib.metadata.version('ponkan-python')); print(ponkan.__version__)"
uvx --from ponkan-python==X.Y.Z ponkan-list-devices
uvx --from "ponkan-python[image]==X.Y.Z" ponkan-raw-to-png --help
```

OpenCV smoke は import cost と wheel size が大きいため、release ごとの必須 gate ではなく、OpenCV-facing change がある場合の conditional gate とする。

```console
uvx --from "ponkan-python[opencv]==X.Y.Z" python -c "import cv2; print(cv2.__version__)"
```

production tag は annotated tag を既定にする。

```console
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

release note は GitHub Release を推奨する。初期実装では自動生成に寄せず、`pypi-release` skill の final report に次を含め、必要なら `gh release create` を実行する。

```text
- version:
- tag:
- release branch / PR:
- merge commit:
- PyPI URL:
- publish workflow run:
- local gates:
- post-publish smoke:
- known limitations:
```

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| skill metadata | frontmatter validation | `.agents/skills/pypi-release` | `quick_validate.py` が成功する |
| docs grep | Python support drift | `docs/publishing.md`, `pyproject.toml` | `>=3.12, <3.14` が残らない |
| docs grep | smoke command pin | `docs/publishing.md` | `==X.Y.Z` 付き command 例がある |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| local release preflight docs | release check command の過不足 | docs 更新後 | `uv lock --check`、`uv build`、`twine check` が明記される |
| skill coordination | `pypi-release` と `pr-merge-cleanup` の責務分離 | skill 更新後 | PR merge 手順は `pr-merge-cleanup` に委譲される |
| no workflow regression | publish workflow の維持 | `.github/workflows/publish.yml` 変更なし | build / publish job 分離と `id-token: write` が維持される |

### 検証コマンド

```console
uv run python -X utf8 C:\Users\train\.codex\skills\.system\skill-creator\scripts\quick_validate.py .agents\skills\pypi-release
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
rg -n ">=3\.12, <3\.14|ponkan-python\[d3xx\]" docs AGENTS.md .agents
git diff --check
```

ドキュメント / skill 変更のみであっても、project policy に合わせて unit test まで実行する。実機 new 3DS XL command はこの Work Unit では実行しない。release smoke で hardware を使う場合は、別途 `n3dsxl-hardware-harness` と人間承認を必要とする。

## 6. 実装チェックリスト

- [ ] `.agents/skills/pypi-release/SKILL.md` を作成する。
- [ ] `.agents/skills/pypi-release/agents/openai.yaml` を作成する。
- [ ] `AGENTS.md` の主要 skill 一覧へ `pypi-release` を追加する。
- [ ] `docs/publishing.md` の Python support drift を修正する。
- [ ] `docs/publishing.md` に release preflight、version policy、tag stop conditions、`twine check`、version-pinned smoke を追加する。
- [ ] release note / GitHub Release の扱いを `docs/publishing.md` と `pypi-release` skill に明記する。
- [ ] `quick_validate.py` で `pypi-release` skill を検証する。
- [ ] format / lint / type / unit / grep / diff check を実行する。
- [ ] 実装結果と gate 結果を本仕様へ反映する。
- [ ] レビュー完了。

## 7. 参照

| 参照 | 用途 |
| ---- | ---- |
| Python Packaging User Guide: Packaging Python Projects, https://packaging.python.org/en/latest/tutorials/packaging-projects/ | `pyproject.toml` metadata、build backend、sdist / wheel、upload flow の一般形。 |
| Python Packaging User Guide: Publishing package distribution releases using GitHub Actions CI/CD workflows, https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/ | GitHub Actions を使う publish workflow の一般形。 |
| PyPI Docs: Publishing with a Trusted Publisher, https://docs.pypi.org/trusted-publishers/using-a-publisher/ | OIDC / Trusted Publishing、`id-token: write`、TestPyPI repository URL の根拠。 |
| PyPA `gh-action-pypi-publish`, https://github.com/pypa/gh-action-pypi-publish | build と publish の分離、artifact 経由、Trusted Publishing、attestation の扱い。 |
| `docs/publishing.md` | 現行 project-local publish docs。 |
| `.github/workflows/publish.yml` | 現行 tag-driven publish workflow。 |
| `.agents/skills/pr-merge-cleanup/SKILL.md` | release PR merge / cleanup の委譲先。 |
| `E:\documents\VSCodeWorkspace\5genSearch-web\.agents\skills\gh-pages-release\SKILL.md` | release workflow skill の構造参考。release-please 依存部分は移植しない。 |
