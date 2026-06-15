# ponkan-python への申し送り事項

状態: 完了済み入力資料。実装対象ではなく、`local_028` 以降の WIP 仕様に採用された内容だけを実装候補として扱う。

注記: この文書の「現行実装」は申し送り作成時点の状態を示す。後続の `local_029` で Windows の `backend="auto"` は `d3xx-native` に解決する方針へ変更済みであり、release 向け migration note は `README.md` と `docs/api.md` に反映する。

Project NyX の capture source として `ponkan-python` を使う前提で、ponkan-python 側に欲しい仕様・API を整理する。今回は NyX 側の個別不満を列挙するのではなく、ponkan-python の現行リファレンス実装を前提に、NyX が将来扱い得る device/profile を増やしても一貫した contract になるように再構成する。

この文書は申し送り用の入力資料であり、後続の `local_028` 以降の仕様書で採用された内容だけを実装対象とする。

## 1. 調査した現行実装

調査対象:

- `E:\documents\VSCodeWorkspace\ponkan-python\pyproject.toml`
- `src/ponkan/__init__.py`
- `src/ponkan/capture.py`
- `src/ponkan/errors.py`
- `src/ponkan/devices/n3dsxl_ftd3.py`
- `src/ponkan/protocol/sizes.py`
- `src/ponkan/protocol/layout_3ds.py`
- `src/ponkan/streaming/engine.py`
- `src/ponkan/streaming/stats.py`
- `docs/api.md`
- `spec/initial/cc3dsfs_python_rebuild_spec.md`

現行 ponkan-python は new 3DS XL capture board の 2D capture に集中している。公開 API は `open_capture()`、`CaptureConfig`、`CaptureOutput`、`CaptureReader`、`capture_sizes()` を中心にしており、OpenCV 風の `get/set/CAP_PROP_*` API は持たない。

現行制約:

| 項目 | 現状 |
|------|------|
| supported model | `new_3ds_xl` のみ |
| source selector | `0` と `"new_3ds_xl"` のみ |
| mode | 2D のみ。`mode_3d=True` は `UnsupportedOperation` |
| backend | 申し送り時点では `auto`, `d3xx`, `d3xx-native`, `libusb` literal があり、high-level opener では `libusb` は unsupported。後続実装では Windows `auto` は `d3xx-native` path |
| output | `top`, `bottom`, `both_vertical` |
| color space | `RGB`, `BGR` |
| read cadence | FPS 制御用の public API はない。reader は backend completion と polling / queue policy に従う |
| device discovery | 申し送り時点では N3DSXL 専用の low-level listing API と CLI のみ。後続実装で profile 横断の `list_capture_devices()` を追加済み |
| error model | exception hierarchy はあるが、GUI が機械的に分岐しやすい `code` / `reason` / `backend` / `profile` 属性は限定的 |

README / docs は、現行 package が old DS、Optimize、Nisetro、IS device、GUI、録画、audio playback を提供しないことを明記している。一方、初期 spec では old 3DS を後続対象として設計枠だけ確保している。classic DS / DS Lite 相当については、現行実装・現行 spec では具体的な protocol / identity / layout が確認できなかったため、NyX 側から要求するなら別途 source audit が必要である。

## 2. NyX から見た責務境界

NyX は Nintendo Switch / 3DS 等の自動化 GUI・runtime・macro framework であり、USB capture board の protocol 実装や device family 判定を抱え込まない。NyX 側が保持したい責務は次に絞る。

| NyX 側責務 | ponkan-python 側に寄せたい責務 |
|------------|-------------------------------|
| capture source の選択 UI | 対応 profile / device family の列挙 |
| runtime への `FrameSourcePort` 接続 | `open_capture()` と reader lifecycle |
| `capture_fps`、表示補正、macro runtime との整合 | output / colorspace / layout metadata の解決 |
| dependency unavailable 時の UI fallback | backend / driver / runtime state の機械判定 |
| user log / status bar 表示 | machine-readable error reason と remediation hint |

NyX は `raw_slots`、queue size、drop policy、poll interval、read timeout などの低レベル tuning を通常 GUI に出さない方針にした。これらは ponkan-python 側の既定値として扱えるのが望ましい。

## 3. 最優先: Profile Registry

N3DSXL 固定の `CaptureConfig` を直接 GUI に露出すると、今後 o3DS / old 3DS / classic DS / other capture board を検討するたびに NyX 側設定が増殖する。まず ponkan-python 側に、device family と capture profile を列挙・解決する public contract が欲しい。

欲しい API 例:

```python
from ponkan import get_capture_profile, list_capture_profiles

profiles = list_capture_profiles()
profile = get_capture_profile("n3dsxl")
```

戻り値イメージ:

```python
CaptureProfile(
    id="n3dsxl",
    display_name="N3DSXL",
    model="new_3ds_xl",
    family="3ds",
    provider="ponkan-python",
    support_status="stable",
    default_output="both_vertical",
    default_colorspace="BGR",
    native_fps=59.834,
    screen_layout="3ds_dual_screen",
    supported_outputs=("top", "bottom", "both_vertical"),
    supports_3d=False,
    supports_audio=False,
    supports_recording=False,
)
```

この例の `default_colorspace="BGR"` は NyX 側の利用希望を示す。ponkan-python 側の採用仕様では、package の既定 `CaptureConfig.colorspace="RGB"` を `default_colorspace` とし、NyX は `colorspace="BGR"` を明示して OpenCV / NyX runtime 側の channel order に合わせる。

profile registry で表現したい family:

| profile / family | 現行根拠 | NyX での扱い |
|------------------|----------|--------------|
| `n3dsxl` / new 3DS XL | 実装済み。現行 public API の主対象 | 表示可能。最初の stable target |
| `old3ds` / old 3DS | 初期 spec に後続対象として設計枠あり。実装は未着手 | `unsupported` または `planned` として metadata に出せるとよい |
| `classic_ds` / DS, DS Lite 等 | 現行実装・spec で protocol 詳細未確認 | API で予約しない。source audit 後に profile 追加を検討 |
| `optimize`, `nisetro`, `is_nitro`, `is_twl`, `partner_ctr` | docs で非対応明記 | `unsupported` として reason を返せると NyX の UI 判断に使える |

NyX は `support_status in {"stable", "experimental"}` だけ通常 UI に表示し、`unsupported` / `planned` は開発者向け diagnostics に留める。

## 4. Backend State in Device Discovery

NyX は現状 `importlib.util.find_spec("ponkan")` だけで GUI の表示可否を決めている。これは package availability の確認としては軽いが、driver / backend runtime / platform の状態までは分からない。

欲しい API は backend state を device discovery に含める形にする:

```python
from ponkan import list_capture_devices

devices = list_capture_devices(profile="n3dsxl", backend="auto")
```

期待する情報:

| 情報 | 用途 |
|------|------|
| resolved backend | `auto` が `d3xx` / `d3xx-native` / other のどれになったかを user log に出す |
| backend availability | GUI に capture source を表示するか、warning に留めるかを決める |
| unavailable reason | `missing_package`, `missing_driver`, `missing_runtime`, `unsupported_platform`, `device_not_found` など |
| remediation hint | PyD3XX / driver / udev / Zadig 等の案内を NyX 側で出す |
| opens device? | discovery が device open や command 送信を行うかどうか |

重要な境界:

- package / backend module / driver service の確認は `open_capture()` より前に軽量に行いたい。
- N3DSXL command を送る確認は explicit open の責務であり、GUI menu 構築では実行しない。
- 後続の `local_029` で Windows high-level / discovery の `auto` は `d3xx-native` 優先へ変更された。この変更は release note / migration note として `README.md` と `docs/api.md` に明記する。

## 5. Device Listing API

NyX の初期実装は physical device selection を scope 外にして `open_capture()` の既定選択に委譲している。複数台接続や profile 横断対応を考えると、ponkan-python 側に stable device identifier を返す public API が必要になる。

欲しい API:

```python
from ponkan import list_capture_devices

devices = list_capture_devices(profile="n3dsxl", backend="auto")
```

戻り値イメージ:

```python
CaptureDeviceInfo(
    id="d3xx:nxl530228",
    display_name="N3DSXL.2 (nxl530228)",
    profile_id="n3dsxl",
    model="new_3ds_xl",
    backend="d3xx",
    vendor_id=0x0403,
    product_id=0x601E,
    serial_number="nxl530228",
    product_string="N3DSXL.2",
    product_string_status="accepted",
    connection_status="available",
)
```

要件:

- listing は N3DSXL command を送らない。
- accepted / rejected / unsupported を機械判定できる。
- product string unreadable のような safety boundary を情報として返す。
- profile が増えても同じ API で扱える。

## 6. Output / Layout Contract

NyX は macro runtime へ 1 枚の BGR frame を渡すため、現在は `CaptureOutput.BOTH_VERTICAL` と `colorspace="BGR"` を使っている。profile が増える場合、画面構成・座標変換・表示補正を NyX が各 device ごとに直書きしないよう、ponkan-python 側から layout metadata が欲しい。

欲しい metadata:

| 情報 | 用途 |
|------|------|
| screen list | `top`, `bottom`, `top_right`, `main`, `touch` など |
| screen size | NyX の preview / coordinate transform |
| default composite | `both_vertical`, `both_horizontal`, `single_main` など |
| coordinate spaces | macro 側で touch/cursor 座標を合わせるため |
| aspect / scale hints | N3DSXL HD aspect box のような表示補正 |
| colorspace default | BGR/RGB の明示 |

`CaptureOutput` は N3DSXL 固定 enum ではなく、profile metadata と整合する output set を返せる形が望ましい。

## 7. Error Model

NyX の GUI は user log / status bar / technical log を分ける。ponkan-python 側 error に structured fields があると、NyX 側で文字列解析せずに扱える。

欲しい共通属性:

```python
class CaptureError(Exception):
    code: str
    profile: str | None
    backend: str | None
    reason: str | None
    recoverable: bool
    remediation: str | None
```

主な reason:

| reason | NyX の扱い |
|--------|------------|
| `missing_package` | capture source を hidden / install guidance |
| `missing_driver` | backend 選択・driver guidance |
| `unsupported_platform` | profile は表示しても disabled |
| `unsupported_profile` | UI に出さない |
| `device_not_found` | source は表示し、未接続 status |
| `device_rejected` | safety warning |
| `open_failed` | preview error |
| `read_failed` | runtime error / reconnect candidate |
| `decode_failed` | technical log + frame source failure |

現行 `D3xxBackendError` は `function` / `status` / `field_name` を持っており参考になる。`DependencyUnavailableError` や `UnsupportedOperation` も同じ粒度の structured context を持つと扱いやすい。

## 8. Support Roadmap と NyX への見せ方

NyX 側 UI は ponkan-python の support status に従って露出を制御したい。

| status | 意味 | NyX UI |
|--------|------|--------|
| `stable` | 実機 E2E / performance gate 済み | 通常表示 |
| `experimental` | 実装あり、検証限定 | advanced / developer toggle |
| `planned` | metadata だけ、実装なし | 非表示。diagnostics のみに出す |
| `unsupported` | 明示的に非対応 | 非表示 |
| `unknown` | source audit 未実施 | 非表示 |

現時点の整理:

| profile | status | 根拠 |
|---------|--------|------|
| `n3dsxl` | `stable` または `experimental` | 実装済み。2D high-level read API / D3XX streaming / tests あり。NyX では初期 target |
| `old3ds` / `o3ds` | `planned` | 初期 spec に設計枠あり。現行 public API には未実装 |
| `classic_ds` | `unknown` | 現行実装・spec で protocol 詳細未確認。別途 source audit が必要 |
| `optimize` / `nisetro` / `is_*` | `unsupported` | docs で非対応明記 |

## 9. NyX 側がこの API を使うときの想定

NyX 側の将来形:

1. 起動時または設定画面表示時に `list_capture_profiles()` を軽量に呼ぶ。
2. `support_status` と device discovery reason を見て、表示可能な capture source だけ menu に出す。
3. profile 選択時は `profile_id` だけ settings に保存する。
4. 既存 `open_capture(output=..., colorspace="BGR")` で reader を開く。
5. structured errors を user log / technical log に反映する。

NyX 側に残す設定:

- `capture_source_type`
- `capture_profile_id`
- `capture_device_id` または auto selection
- `capture_fps`
- NyX 固有の display transform / macro coordinate transform

NyX 側から消したい、または advanced file-only に留めたい設定:

- `capture_provider`
- `ponkan_raw_slots`
- `ponkan_output_queue_size`
- `ponkan_drop_policy`
- `ponkan_poll_interval`
- `ponkan_read_timeout`
- `ponkan_collect_timing`

## 10. 依頼の優先順位

NyX 連携としての優先順位:

1. `list_capture_profiles()` / `CaptureProfile` / support status
2. backend state を含む profile 横断の `list_capture_devices()`
3. structured `CaptureError`
4. output / layout metadata
5. old 3DS / o3DS / classic DS 等の source audit と profile 追加

この順番なら、NyX は N3DSXL 固定実装から profile-driven UI に移行でき、将来の device support が増えても GUI 設定や runtime adapter の責務が破綻しにくい。
