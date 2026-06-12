---
name: pypi-release
description: "ponkan-python の PyPI release を計画・実行する workflow skill。USE WHEN: ユーザが PyPI へのデプロイ、ライブラリのバージョンアップ、release tag 作成、TestPyPI / PyPI publish、post-publish smoke check、release 手順の確認を依頼したとき。"
---

# PyPI Release

`ponkan-python` の release preflight、version bump PR、tag-driven PyPI publish、post-publish smoke check を進める。
upload は手元の `twine upload` ではなく、`.github/workflows/publish.yml` の GitHub Actions Trusted Publishing に統一する。

## Inputs

| 入力 | 扱い |
| ---- | ---- |
| `version` | 明示されたらその version を候補にする。未指定なら latest tag と未リリース commit から提案する。 |
| `releaseType` | `patch` / `minor` / `major`。未指定なら変更内容から提案する。 |
| `includeTestPyPI` | 明示された場合のみ TestPyPI workflow を通す。高リスク変更では実行を提案する。 |
| `createGitHubRelease` | 既定で提案する。不要と明示されたら final report だけにする。 |
| `hardwareSmoke` | 実機 smoke は人間承認と `n3dsxl-hardware-harness` なしでは実行しない。 |

## Preconditions

- `git status --short` が clean であること。
- GitHub remote と default branch を確認できること。
- `docs/publishing.md` と `.github/workflows/publish.yml` が存在すること。
- PyPI / TestPyPI の Trusted Publisher が project / owner / repository / workflow / environment に一致していること。
- production PyPI は tag push でのみ publish すること。`workflow_dispatch` は TestPyPI 専用として扱う。

## Preflight

1. `git branch --show-current` と `git status --short --branch` を確認する。
2. default branch と `origin/<default>` を確認し、release PR 作成時は `release/vX.Y.Z` branch を使う。
3. `git fetch --tags origin` で tag を更新する。
4. `git tag --list "v*" --sort=-version:refname` と `git log --oneline --no-merges <latest-tag>..HEAD` で未リリース差分を読む。
5. `pyproject.toml`、`uv.lock`、`docs/publishing.md` の package name / version / Python support / optional extras の drift を確認する。
6. PyPI の version-specific JSON endpoint で候補 version が未公開であることを確認する。
7. release tag が local / remote に存在しないことを確認する。

## Version Policy

| 条件 | 既定の release type |
| ---- | ------------------- |
| docs、metadata、bug fix、dependency metadata cleanup | `patch` |
| 後方互換の public API / CLI 追加 | `minor` |
| import package、public API、CLI、dependency surface の破壊的変更 | `major` または pre-1.0 の explicit version |

`feat` commit があるのに `patch` を選ぶ場合、理由を release plan に書く。
`BREAKING CHANGE` または `!` 付き commit があるのに `minor` 以下を選ぶ場合、中断して user に確認する。

## Release PR

1. `release/vX.Y.Z` branch を作る。
2. `pyproject.toml` の project version を更新する。
3. `uv lock` で `uv.lock` を同期する。
4. `docs/publishing.md` の例、release note draft、必要な docs を更新する。
5. stale distribution artifact を削除し、local gates を実行する。`dist/.gitignore` は残し、過去 version の wheel / sdist は削除する。

```console
uv sync --dev
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
Remove-Item -ErrorAction SilentlyContinue dist\ponkan_python-*.whl, dist\ponkan_python-*.tar.gz
uv build
uvx --from twine twine check dist\ponkan_python-X.Y.Z-py3-none-any.whl dist\ponkan_python-X.Y.Z.tar.gz
git diff --check
```

6. wheel content を candidate version 固定で確認する。`next(Path("dist").glob("*.whl"))` のような曖昧な選択は、古い artifact を誤検査するため使わない。最低限 `ponkan/__init__.py` と `ponkan/py.typed` が wheel に含まれ、`py3dscapture/` が含まれないことを確認する。
7. PR 作成、merge、default branch 同期、branch cleanup は `pr-merge-cleanup` に委譲する。

## TestPyPI

- TestPyPI は `Publish` workflow の `workflow_dispatch` path で実行する。
- TestPyPI を実行しても production PyPI は更新されない。
- TestPyPI の dependency resolution は本番 PyPI と完全には一致しないため、最終判断は production publish 後の smoke check で行う。

## Production Publish

1. release PR が merge 済みで、local default branch が `origin/<default>` と同期していることを確認する。
2. candidate version が PyPI に未公開で、`vX.Y.Z` tag が存在しないことを再確認する。
3. production publish の明示意図が current turn にない場合、tag push 前に user に確認する。
4. annotated tag を作成して push する。

```console
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

5. `Publish` workflow run を確認する。build failure と publish failure を分けて読む。
6. build と `twine check` が通った後の `requests.exceptions.ChunkedEncodingError` など attestation / network 系 failure は、metadata 変更ではなく failed job rerun 候補として扱う。

## Post-Publish

1. version-specific endpoint を確認する。

```text
https://pypi.org/pypi/ponkan-python/X.Y.Z/json
```

2. version-pinned smoke check を行う。

```console
uvx --from ponkan-python==X.Y.Z python -c "import importlib.metadata, ponkan; print(importlib.metadata.version('ponkan-python')); print(ponkan.__version__)"
uvx --from ponkan-python==X.Y.Z ponkan-list-devices
uvx --from "ponkan-python[image]==X.Y.Z" ponkan-raw-to-png --help
```

3. OpenCV-facing change がある場合のみ OpenCV extra を確認する。

```console
uvx --from "ponkan-python[opencv]==X.Y.Z" python -c "import cv2; print(cv2.__version__)"
```

4. GitHub Release を作る場合は、version、tag、PR、merge commit、PyPI URL、workflow run、local gates、smoke 結果、known limitations を含める。

## Stop Conditions

- dirty worktree がある。
- default branch が `origin/<default>` と同期していない。
- candidate version が PyPI に既に存在する。
- local または remote に release tag が既に存在する。
- `pyproject.toml`、`uv.lock`、`docs/publishing.md` の metadata が矛盾している。
- local gate、CI、publish workflow が失敗している。
- production tag push の明示意図がない。
- 実機 smoke が必要だが、人間承認と `PONKAN_HARDWARE_APPROVED=1` がない。

## Report

最終報告には次を含める。

```text
- version:
- release type:
- release branch / PR:
- tag:
- merge commit:
- PyPI URL:
- publish workflow run:
- local gates:
- post-publish smoke:
- GitHub Release:
- hardware: used | not used | not run with reason
- follow-up:
```
