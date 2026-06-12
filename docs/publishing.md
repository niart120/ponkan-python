# Publishing

This project is prepared for PyPI publication with local builds and GitHub
Actions Trusted Publishing. No PyPI API token is required when the PyPI project
has a matching trusted publisher.

## Package Metadata

- Distribution name: `ponkan-python`
- Import package: `ponkan`
- Python support: `>=3.12, <3.14`
- License expression: `MIT`
- License files: `LICENSE`, `NOTICE.md`
- Repository: `https://github.com/niart120/ponkan-python`
- Publish workflow: `.github/workflows/publish.yml`

## Local Release Check

Run these checks before creating a release tag:

```console
uv sync --dev
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
uv build
```

The build should create both an sdist and wheel under `dist/`.

## TestPyPI

Create a Trusted Publisher for TestPyPI with:

| Field | Value |
| --- | --- |
| Project name | `ponkan-python` |
| Owner | `niart120` |
| Repository name | `ponkan-python` |
| Workflow filename | `publish.yml` |
| Environment name | `testpypi` |

Then run the `Publish` workflow manually from GitHub Actions. The manual
workflow path publishes only to TestPyPI.

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
After the project and trusted publisher are ready, pushing a version tag starts
the PyPI publish job:

```console
git tag v0.1.1
git push origin v0.1.1
```

The workflow builds the distribution once, stores it as a workflow artifact, and
publishes the same artifact to the selected package index.

## Post-Publish Smoke Check

After upload, verify installation in a clean environment:

```console
uvx --from ponkan-python ponkan-list-devices
```

For optional features:

```console
uvx --from "ponkan-python[image]" ponkan-raw-to-png --help
```

On Windows, the D3XX backend dependency is installed through normal platform
metadata. Use `uvx --from ponkan-python ponkan-list-devices` for the D3XX
smoke check.
