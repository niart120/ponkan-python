# N3DSXL Raw Capture Fixture And Decoder 仕様書

更新日: 2026-06-07

## 1. 概要

### 1.1 目的

Step 5-6 として、2D mode の単発 raw frame を取得し、`.bin` と `.json` metadata として保存し、raw video 領域を top / bottom の RGB8 ndarray と PNG へ変換する。

この Work Unit は MVP の完了条件ではなく、async streaming の前に必要な bring-up gate として扱う。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| RawCapture | 実機から得た raw transfer payload と metadata を保持する data model。 |
| Raw Fixture | 回帰テスト用に保存する `.bin` と `.json` の組。 |
| Video Region | raw payload 先頭 `video_size` bytes。2D では `518400` bytes。 |
| CaptureFrame | 利用者へ返す top / bottom / top_right ndarray の data model。 |
| Decoder Candidate | raw layout の転置、回転、flip 仮説を比較する decoder variant。 |
| Decoder Version | 手動目視で承認した layout 変換を固定する識別子。 |
| Manual Visual Gate | PNG の向き、色順、画面分割を人間が確認する gate。 |

### 1.3 背景・問題

raw capture struct には video、audio、unused buffer、error buffer が含まれる。MVP では audio playback を扱わないが、raw fixture と metadata には存在を記録する必要がある。また、raw video layout は最終表示の向きと一致しない可能性が高いため、初回 decoder は複数 candidate を出力し、手動目視で確定する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| raw 証拠 | 実装なし | decoder 前の `.bin` と metadata を保存できる |
| decode 回帰 | 実装なし | raw fixture から実機なしで ndarray shape/dtype を検証できる |
| layout 仮説 | 初期仕様に pending | candidate PNG を出力し、承認済み decoder_version を固定する |
| async 前 gate | なし | streaming 実装前に 1 frame capture と decoder を通す |

### 1.5 着手条件

- [x] `spec/complete/local_011/N3DSXL_FTD3_PIPE_AND_CONNECT.md` の 2D connect が実装済み。
- [x] capture struct size と payload slicing の source audit 状態が確認済み。
- [ ] raw capture を実行する場合、人間承認と artifact 保存先が決まっている。

### 1.6 Work Unit メタデータ

| 項目 | 内容 |
| ---- | ---- |
| 配置 | `spec/complete/local_012/N3DSXL_RAW_CAPTURE_FIXTURE_AND_DECODER.md` |
| 対応 Step | Step 5: single raw frame capture、Step 6: decoder and PNG |
| 前提 Work Unit | `spec/complete/local_011/N3DSXL_FTD3_PIPE_AND_CONNECT.md` |
| 次 Work Unit | `spec/complete/local_013/N3DSXL_ASYNC_STREAMING_ENGINE.md` |
| local task | RawCapture metadata、transfer validation、synthetic decoder、Pillow/colorspace adapter。 |
| hardware task | raw_2d fixture capture、candidate PNG、manual visual approval。 |
| 選択条件 | 2D connect が完了し、streaming 前の raw artifact / decoder evidence が未確定のとき。 |
| 完了証拠 | raw fixture 保存方針、decoder_version、manual visual 状態が metadata または gate 報告に残る。 |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `src/py3dscapture/protocol/n3dsxl.py` | 修正 | `read_raw_frame(mode_3d=False)` を追加する。 |
| `src/py3dscapture/capture.py` | 新規 | public open API と raw capture 操作を整理する。 |
| `src/py3dscapture/image/frame.py` | 新規 | `CaptureFrame` data model と adapter を定義する。 |
| `src/py3dscapture/protocol/layout_3ds.py` | 新規 | raw RGB8 video buffer を top/bottom に変換する。 |
| `src/py3dscapture/tools/capture_raw.py` | 新規 | raw capture CLI を提供する。 |
| `src/py3dscapture/tools/raw_to_png.py` | 新規 | raw fixture から PNG を出力する。 |
| `tests/unit/test_raw_capture_metadata.py` | 新規 | metadata schema と validation を検証する。 |
| `tests/unit/test_layout_3ds_decoder.py` | 新規 | synthetic / golden fixture で decoder を検証する。 |
| `tests/e2e/test_n3dsxl_raw_capture.py` | 新規 | 実機 raw capture と fixture 保存を検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| 2D raw frame を読む | connected N3DSXL、`mode_3d=False` | `RawCapture` を返す | streaming 前 bring-up |
| 3D raw frame を明示扱いする | `mode_3d=True` | 3D capture は後続対象として明示。MVP streaming 中切替は拒否 | 単発 3D は後続 |
| transferred を検証する | raw transfer length | `video_size <= transferred <= capture_size` を満たす | error buffer 疑いを記録 |
| video region を切り出す | `RawCapture.payload` | 先頭 `video_size` bytes を decoder に渡す | audio は metadata に残す |
| raw fixture を保存する | RawCapture、出力 path | `.bin` と `.json` を保存する | decoder に失敗しても raw は残す |
| metadata を保存する | RawCapture | model、VID/PID、product string、mode、transferred、video_size、capture_size、sequence を含む | json |
| 2D decoder を実行する | `518400` bytes | top shape `(240, 400, 3)`、bottom shape `(240, 320, 3)`、dtype `uint8` | RGB |
| decoder candidate を出力する | raw fixture | candidate ごとの PNG を出力する | manual visual |
| decoder_version を固定する | 目視承認済み candidate | metadata に `decoder_version` と `manual_visual_status` を記録する | golden corpus |
| Pillow へ変換する | `CaptureFrame.to_pillow()` | optional dependency がある場合に `Image` を返す | import は遅延 |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | RawCapture metadata に必須 key が含まれる | new behavior | 3.1 | unit |
| green | transferred が video_size 未満なら error になる | regression | 3.1 | unit |
| green | transferred が capture_size 超過なら error になる | regression | 3.1 | unit |
| green | video region は payload 先頭 video_size bytes だけを返す | new behavior | 3.1 | unit |
| green | 2D synthetic raw を top/bottom shape に分割できる | new behavior | 3.1 | unit |
| green | `to_ndarray(colorspace="BGR")` が channel order を変換する | new behavior | 3.1 | unit |
| green | Pillow 未導入時の `to_pillow()` error が分かりやすい | regression | 3.1 | optional dependency |
| green | `raw_to_png` が candidate PNG を複数出力する | new behavior | 3.1 | CLI |
| deferred | 実機 raw_2d_001.bin と raw_2d_001.json を保存できる | hardware | 3.1 | `requires_n3dsxl`。人間承認待ち |
| deferred | manual visual check で decoder_version を metadata に残す | manual_visual | 3.1 | 人間確認待ち |

### 3.3 設計方針

raw capture と decoder を分離する。`read_raw_frame()` は raw transfer と metadata を返し、画像変換は `layout_3ds.py` と `image/frame.py` に置く。

Source Audit:

| 項目 | 参照元候補 | 状態 |
| ---- | ---------- | ---- |
| `FTD3_3DSCaptureReceived` / `_3D` struct | `include/capture_structs.hpp` | video、audio、unused、error buffer 構造を確認 |
| `N3DSXL_SAMPLES_IN` | `include/hw_defs.hpp` | `1096 * 16` を確認。Step 0 size 計算と一致 |
| raw video layout | `capture_structs.hpp` と `hw_defs.hpp` | 2D raw video size `240 * 720 * 3` を確認。最終 transform は manual visual で確定 |
| decoder transform | 実機 PNG 目視 | 未確定。candidate 出力と `manual_visual_status=pending` を実装 |

Hardware:

| 項目 | 扱い |
| ---- | ---- |
| raw capture | `@pytest.mark.requires_n3dsxl`、人間承認必須 |
| fixture 保存 | artifact path と上書き可否を事前に説明する |
| manual visual | `@pytest.mark.manual_visual` または明示的な報告として扱う |

### 3.4 Agentic SDD Task Graph

| 分類 | Task | Gate |
| ---- | ---- | ---- |
| Blocking local task | RawCapture metadata schema と JSON serializer を TDD 実装する | metadata unit test |
| Blocking local task | transferred validation と video region slicing を実装する | validation unit test |
| Blocking local task | synthetic raw で top/bottom shape と dtype を固定する | decoder unit test |
| Sidecar task | capture struct と raw layout の source audit を行う | source audit note |
| Hardware task | `raw_2d_001.bin` と `.json` を保存する | human approval、artifact |
| Hardware task | candidate PNG を出して manual visual で decoder_version を固定する | manual_visual result |

この仕様は continuous streaming を実装しない。raw frame 取得は bring-up gate であり、MVP acceptance は `local_013` と `local_014` まで進んだ時点で判断する。

## 4. 実装仕様

### 4.1 RawCapture

```python
@dataclass(slots=True)
class RawCapture:
    model: Literal["new_3ds_xl"]
    mode_3d: bool
    payload: bytes
    transferred: int
    video_size: int
    capture_size: int
    timestamp_ns: int | None
    sequence: int | None
    metadata: dict[str, object]
```

metadata schema:

```json
{
  "model": "new_3ds_xl",
  "product_string": "N3DSXL",
  "vid": "0x0403",
  "pid": "0x601f",
  "mode_3d": false,
  "transferred": 553984,
  "video_size": 518400,
  "capture_size": 555008,
  "sequence": 1,
  "timestamp_ns": 0,
  "decoder_version": null,
  "manual_visual_status": "pending"
}
```

### 4.2 CaptureFrame

```python
ColorSpace = Literal["RGB", "BGR"]
ScreenName = Literal["top", "bottom", "top_right"]

@dataclass(slots=True)
class CaptureFrame:
    top: np.ndarray
    bottom: np.ndarray
    top_right: np.ndarray | None
    timestamp_ns: int | None
    source_model: Literal["new_3ds_xl", "old_3ds"]
    mode_3d: bool
    sequence: int | None = None
    colorspace: ColorSpace = "RGB"

    def to_ndarray(self, screen: ScreenName = "top", colorspace: ColorSpace = "RGB") -> np.ndarray: ...
    def to_pillow(self, screen: ScreenName = "top"): ...
    def to_mosaic(self, gap: int = 0) -> np.ndarray: ...
```

constraints:

```text
top.shape == (240, 400, 3)
bottom.shape == (240, 320, 3)
top.dtype == np.uint8
bottom.dtype == np.uint8
colorspace == "RGB"
```

### 4.3 Decoder Candidate

```python
class DecoderVersion(IntEnum):
    RESHAPE_ONLY = 0
    TRANSPOSE = 1
    ROTATE90 = 2
    ROTATE90_FLIP = 3

def decode_rgb8_2d(raw_video: bytes | memoryview, *, decoder_version: int) -> CaptureFrame: ...
def iter_decoder_candidates(raw_video: bytes | memoryview) -> Iterable[tuple[int, CaptureFrame]]: ...
```

candidate は初回実機 raw fixture で比較する。承認済み version が決まるまで、public streaming API の既定 decoder として固定しない。

### 4.4 CLI

raw capture:

```console
uv run python -m py3dscapture.tools.capture_raw --model new_3ds_xl --out tests/fixtures/n3dsxl/raw_2d_001.bin
```

raw to PNG:

```console
uv run python -m py3dscapture.tools.raw_to_png tests/fixtures/n3dsxl/raw_2d_001.bin --metadata tests/fixtures/n3dsxl/raw_2d_001.json --out tests/fixtures/n3dsxl/
```

`capture_raw` は `.bin` と `.json` を同じ stem で保存する。既存 file 上書きは `--force` なしでは拒否する。

### 4.5 完了判定

| 判定 | 必須 evidence |
| ---- | ------------- |
| local complete | metadata、validation、decoder、colorspace の unit test が通る |
| raw fixture pending | 実機 raw capture の command scope、保存先、上書き policy、cleanup を示して承認待ち |
| raw fixture complete | `.bin` と `.json` の path、transferred、video_size、capture_size、product string を報告 |
| decoder approved | candidate PNG と manual visual result、承認済み `decoder_version` を metadata に残す |

実装結果:

| 項目 | Evidence |
| ---- | -------- |
| source-audit complete | `include/capture_structs.hpp` と `include/hw_defs.hpp` を確認し、metadata / size validation / decoder candidate に反映 |
| local complete | `uv run pytest tests\unit\test_raw_capture_metadata.py tests\unit\test_layout_3ds_decoder.py -q` が 12 passed |
| unit regression | `uv run pytest tests\unit -q` が 39 passed |
| static | `uv run ruff format --check .`、`uv run ruff check src tests`、`uv run ty check --no-progress` が pass |
| raw fixture pending | `uv run pytest tests\e2e -q` は `PONKAN_RUN_N3DSXL` 未設定で 4 skipped。実機 raw capture は未実行 |
| manual visual pending | candidate PNG 出力 CLI は local test 済み。実機 PNG の目視承認と `decoder_version` 固定は未実行 |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| metadata builder | 必須 key | RawCapture | JSON serializable |
| transfer validation | too short | `transferred=518399` | error |
| transfer validation | too long | `transferred=555009` | error |
| video slicing | payload with suffix | `video_size=518400` | 先頭だけ |
| decoder | synthetic 2D data | bytes length 518400 | top/bottom shape |
| colorspace | RGB -> BGR | known pixel | channel reversed |
| pillow adapter | optional dependency | installed / missing | Image or clear error |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| raw capture E2E | `.bin` / `.json` 保存 | human approval | raw fixture が残る |
| raw_to_png | candidate PNG 出力 | raw fixture | top/bottom PNG が生成される |
| manual visual | 向き・色・分割 | generated PNG | approved decoder_version |

### 検証コマンド

```console
uv run pytest tests/unit/test_raw_capture_metadata.py tests/unit/test_layout_3ds_decoder.py
uv run ruff check src/py3dscapture tests/unit/test_raw_capture_metadata.py tests/unit/test_layout_3ds_decoder.py
uv run ty check --no-progress
```

実機 gate:

```console
$env:PONKAN_RUN_N3DSXL = "1"
$env:PONKAN_HARDWARE_APPROVED = "1"
uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_raw_capture.py
```

manual visual:

```console
uv run python -m py3dscapture.tools.raw_to_png tests/fixtures/n3dsxl/raw_2d_001.bin --metadata tests/fixtures/n3dsxl/raw_2d_001.json --out tests/fixtures/n3dsxl/
```

## 6. 実装チェックリスト

- [x] capture struct と raw layout の source audit を記録する。
- [x] RawCapture metadata unit test を書く。
- [x] transfer length validation を実装する。
- [x] 2D decoder の synthetic unit test を書く。
- [x] `CaptureFrame` と colorspace adapter を実装する。
- [x] `capture_raw` CLI を実装する。
- [x] `raw_to_png` CLI と decoder candidate 出力を実装する。
- [x] 実機 raw fixture 保存 gate は人間承認まで未実行として報告する。
- [x] manual visual の結果は pending として metadata と gate 報告に残す。
