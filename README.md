# ponkan-python

`ponkan-python` は、new 3DS XL capture board から USB 経由で映像フレームを取得するための Python ライブラリです。

このプロジェクトは [`cc3dsfs`](https://github.com/Lorenzooone/cc3dsfs) を参照しながら、個人用途で必要な N3DSXL 映像取得機能に絞って Python で再構成するものです。`cc3dsfs` 全体の代替や互換 API を提供することは目的にしていません。継続的なメンテナンスや対応 device の拡張は未定です。

## Current Scope

- new 3DS XL capture board の device 認識
- raw frame 取得
- raw frame の保存と metadata 記録
- RGB8 `numpy.ndarray` への変換
- Pillow 互換出力
- libusb async transfer による streaming MVP

詳細は次の仕様書を参照してください。

- `spec/initial/cc3dsfs_python_rebuild_spec.md`
- `spec/initial/cc3dsfs_python_n3dsxl_implementation_workflow.md`

## Development

Python 実行と依存管理は `uv` を使います。

```console
uv sync --dev
uv run ruff format --check .
uv run ruff check .
uv run ty check src/py3dscapture --output-format concise --no-progress
uv run pytest tests/unit
```

実機 new 3DS XL capture board を使うテストは通常 CI では実行しません。

```console
$env:PONKAN_RUN_N3DSXL = "1"
uv run pytest -m requires_n3dsxl tests/e2e
```

## Safety

N3DSXL command は、VID/PID と product string が仕様で許可された device にだけ送ります。未知の FTDI device を N3DSXL として扱わないでください。

## License and Attribution

This project is licensed under the MIT License.

This project references `cc3dsfs` by Lorenzooone:

- https://github.com/Lorenzooone/cc3dsfs
