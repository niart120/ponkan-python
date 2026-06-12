# Publishing

This project publishes `ponkan-python` to PyPI with local release checks and
GitHub Actions Trusted Publishing. Do not upload distributions from a local
machine with `twine upload`; production publishing is driven by a `v*` tag.

## Package Metadata

- Distribution name: `ponkan-python`
- Import package: `ponkan`
- Python support: `>=3.12`
- License expression: `MIT`
- License files: `LICENSE`, `NOTICE.md`
- Repository: `https://github.com/niart120/ponkan-python`
- Publish workflow: `.github/workflows/publish.yml`
- Build backend: Hatchling

## Release Flow

Use this order for normal releases:

1. Confirm the current branch and `git status --short --branch`.
2. Fetch tags and inspect the commits since the latest `v*` tag.
3. Choose the next version and release type.
4. Prepare a `release/vX.Y.Z` branch with the version bump and release docs.
5. Run the local release checks.
6. Merge the release PR through the normal PR workflow.
7. Sync the default branch locally.
8. Create and push an annotated `vX.Y.Z` tag.
9. Confirm the `Publish` workflow and PyPI version.
10. Run version-pinned smoke checks.
11. Create a GitHub Release or record the final release report.

## Version Policy

| Change type | Default release type |
| ----------- | -------------------- |
| Documentation, metadata cleanup, bug fix, dependency metadata cleanup | patch |
| Backward-compatible public API or CLI addition | minor |
| Breaking import package, public API, CLI, or dependency surface change | major or explicit pre-1.0 version |

If a patch release contains a `feat` commit, document why the change is still a
patch. Stop and ask before publishing a `minor` or `patch` release that contains
`BREAKING CHANGE` or `!` commit markers.

## Release Preflight

Before creating a release tag:

- Confirm `pyproject.toml`, `uv.lock`, and this file agree on the project name,
  version, Python support, and optional extras.
- Confirm the candidate PyPI version is not already published by checking the
  version-specific JSON endpoint:
  `https://pypi.org/pypi/ponkan-python/X.Y.Z/json`.
- Confirm neither local nor remote already has the `vX.Y.Z` tag.
- Confirm `.github/workflows/publish.yml` still builds distributions once and
  publishes the stored artifact through `pypa/gh-action-pypi-publish@release/v1`.

Run these checks before creating the release PR or tag:

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

The cleanup keeps `dist/.gitignore` and removes stale wheel / sdist artifacts
from earlier releases. The build should create both an sdist and a wheel for the
candidate version under `dist/`. Check the candidate wheel by exact path; do not
use `next(Path("dist").glob("*.whl"))`, because stale artifacts can make that
select an older release.

```console
uv run python -c "import pathlib, zipfile; wheel=pathlib.Path('dist/ponkan_python-X.Y.Z-py3-none-any.whl'); assert wheel.exists(); names=set(zipfile.ZipFile(wheel).namelist()); assert 'ponkan/__init__.py' in names; assert 'ponkan/py.typed' in names; assert not any(name.startswith('py3dscapture/') for name in names)"
```

## TestPyPI

Create a Trusted Publisher for TestPyPI with:

| Field | Value |
| --- | --- |
| Project name | `ponkan-python` |
| Owner | `niart120` |
| Repository name | `ponkan-python` |
| Workflow filename | `publish.yml` |
| Environment name | `testpypi` |

Run the `Publish` workflow manually from GitHub Actions when a staging publish is
needed. The manual workflow path publishes only to TestPyPI.

TestPyPI is optional for low-risk patch releases, but should be considered for
new package metadata, new dependencies, or packaging workflow changes.

## PyPI

Create or configure the PyPI project and Trusted Publisher with:

| Field | Value |
| --- | --- |
| Project name | `ponkan-python` |
| Owner | `niart120` |
| Repository name | `ponkan-python` |
| Workflow filename | `publish.yml` |
| Environment name | `pypi` |

The `pypi` GitHub environment should require manual approval before deployment.
After the release PR is merged and the default branch is synchronized locally,
create and push an annotated release tag:

```console
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

The tag push starts the PyPI publish job. The workflow builds the distribution
once, stores it as a workflow artifact, and publishes the same artifact to PyPI.

## Stop Conditions

Stop before tag push when any of these are true:

- `git status --short` is not clean.
- The default branch is not synchronized with `origin/<default>`.
- The candidate version already exists on PyPI.
- The candidate `vX.Y.Z` tag already exists locally or remotely.
- `pyproject.toml`, `uv.lock`, and publishing docs disagree.
- A local release check, PR check, or publish workflow job failed.
- Production publish was not explicitly requested or confirmed.
- Hardware smoke is required but human approval is missing.

If the publish job fails after build and metadata checks already passed, inspect
the failed step before changing package metadata. Transient attestation or
network failures, such as `requests.exceptions.ChunkedEncodingError`, are rerun
candidates.

## Post-Publish Smoke Check

Verify the exact published version first:

```text
https://pypi.org/pypi/ponkan-python/X.Y.Z/json
```

Then run version-pinned installation checks in clean `uvx` environments:

```console
uvx --from ponkan-python==X.Y.Z python -c "import importlib.metadata, ponkan; print(importlib.metadata.version('ponkan-python')); print(ponkan.__version__)"
uvx --from ponkan-python==X.Y.Z ponkan-list-devices
```

For the `image` extra:

```console
uvx --from "ponkan-python[image]==X.Y.Z" ponkan-raw-to-png --help
```

On Windows, the D3XX backend dependency is installed through normal platform
metadata. Use `uvx --from ponkan-python==X.Y.Z ponkan-list-devices` for the D3XX
dependency smoke check.

Only run the OpenCV extra smoke when a release changes OpenCV-facing behavior or
metadata:

```console
uvx --from "ponkan-python[opencv]==X.Y.Z" python -c "import cv2; print(cv2.__version__)"
```

Do not rely on the generic latest PyPI JSON endpoint immediately after a fresh
publish; it can lag. Prefer the version-specific endpoint.

## Release Report

After a successful publish, create a GitHub Release or record a final release
report with:

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
