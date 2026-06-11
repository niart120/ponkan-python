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

## Installation

Python 3.12 / 3.13 を対象にしています。

```console
pip install ponkan-python
```

PNG 変換には Pillow extra、FTDI D3XX backend には D3XX extra を追加します。

```console
pip install "ponkan-python[image]"
pip install "ponkan-python[d3xx]"
```

## Usage

高レベル API では、new 3DS XL capture board を開いて `read()` で RGB8 `numpy.ndarray` を取得できます。

```python
from ponkan import CaptureOutput, open_capture

with open_capture(output=CaptureOutput.BOTH_VERTICAL) as cap:
    image = cap.read()
    if image is not None:
        print(image.shape)
```

上画面だけを読む場合は `CaptureOutput.TOP` を指定します。OpenCV へ渡す場合は `colorspace="BGR"` を指定できます。

```python
from ponkan import CaptureOutput, open_capture

with open_capture(output=CaptureOutput.TOP, colorspace="BGR") as cap:
    top_bgr = cap.read()
```

3DS 固有の上画面・下画面・sequence などが必要な場合は `read_frame()` を使います。

```python
from ponkan import open_capture

with open_capture() as cap:
    frame = cap.read_frame()
    if frame is not None:
        top = frame.top
        bottom = frame.bottom
```

API の詳細は [API Reference](https://github.com/niart120/ponkan-python/blob/master/docs/api.md) を参照してください。

## Command Line Tools

インストール後は次の console scripts を利用できます。

```console
ponkan-list-devices
ponkan-capture-raw --out captures/n3dsxl/raw_2d_001.bin
ponkan-raw-to-png captures/n3dsxl/raw_2d_001.bin --metadata captures/n3dsxl/raw_2d_001.json --out captures/n3dsxl/png
ponkan-stream-n3dsxl --duration 10 --stats
```

実機へ N3DSXL command を送る操作は、事前に device identity と安全境界を確認してから実行してください。

## Development

Python 実行と依存管理は `uv` を使います。

```console
uv sync --dev
scripts/install-git-hooks.ps1
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

実機 new 3DS XL capture board を使うテストは通常 CI では実行しません。

```console
$env:PONKAN_RUN_N3DSXL = "1"
uv run pytest -m requires_n3dsxl tests/e2e
```

## Safety

N3DSXL command は、VID/PID と product string が仕様で許可された device にだけ送ります。未知の FTDI device を N3DSXL として扱わないでください。

Git hooks は `.githooks/` に配置しています。clone 後に `scripts/install-git-hooks.ps1` または `sh scripts/install-git-hooks.sh` を実行すると、`core.hooksPath` が `.githooks` に設定されます。

Codex project-local policy は `.codex/` に配置しています。Codex で有効にするには、この project layer を trust し、`/hooks` で hook を review/trust してください。

## License and Attribution

This project is licensed under the MIT License.

This project references `cc3dsfs` by Lorenzooone, which is also licensed under
the MIT License. The upstream copyright notice is preserved in `LICENSE` and
`NOTICE.md`.

- https://github.com/Lorenzooone/cc3dsfs

Release and publishing notes are kept in [Publishing](https://github.com/niart120/ponkan-python/blob/master/docs/publishing.md).
