# N3DSXL Unreadable Product String Policy 仕様書

## 1. 概要

### 1.1 目的

new 3DS XL capture board の USB product string が libusb 経由で読めない場合でも、許可済み VID/PID と明示的な実機 gate に基づいて検証を進められるようにする。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| Accepted VID/PID | `0x0403` と `0x601e`, `0x601f`, `0x602a`, `0x602b`, `0x602c`, `0x602d`, `0x602f` の組み合わせ。 |
| Accepted product string | `N3DSXL` または `N3DSXL.2`。 |
| Unreadable product string | libusb / usb1 descriptor read が失敗し、product string を `None` として扱う状態。 |
| Product string status | `accepted` または `unreadable` の identity evidence。 |

### 1.3 背景・問題

実機 probe で `0x0403:0x601e` の device が見つかったが、libusb 経由の product string が読めず、既存の device filter では `product_string_unreadable` として拒否された。対象 capture board は fan-made device に近く、product string を常に定義・取得できるとは限らない。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| 実機 listing | `product_string_unreadable` で rejected | accepted VID/PID なら unreadable candidate として表示 |
| 誤 device 防止 | product string 必須 | readable unsupported product string は引き続き拒否 |
| 記録性 | product string のみ記録 | product string と status を metadata に記録 |

### 1.5 着手条件

- [x] Accepted VID/PID と accepted product string の定数が存在する。
- [x] 実機 test が `requires_n3dsxl` と env gate で CI から分離されている。
- [x] 人間承認後にだけ `PONKAN_HARDWARE_APPROVED=1` を付けて実機 command を実行する policy が存在する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `src/py3dscapture/devices/n3dsxl_ftd3.py` | 修正 | unreadable product string を candidate 化し、status を保持する。 |
| `src/py3dscapture/transport/libusb_backend.py` | 修正 | product descriptor retry と open matching の conservative rule を追加する。 |
| `src/py3dscapture/hardware_gate.py` | 修正 | unreadable status を許可条件と command plan に記録する。 |
| `src/py3dscapture/protocol/n3dsxl.py` | 修正 | raw metadata に product string status を含める。 |
| `src/py3dscapture/streaming/stats.py` | 修正 | performance stats に product string status を含める。 |
| `src/py3dscapture/tools/*.py` | 修正 | listing / streaming CLI 表示と引数を status 対応にする。 |
| `AGENTS.md`, `.agents/skills/n3dsxl-hardware-harness/SKILL.md` | 修正 | 実機安全制約を新 policy に更新する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| accepted product string | accepted VID/PID + `N3DSXL` / `N3DSXL.2` | candidate `product_string_status="accepted"` | 従来互換 |
| unreadable product string | accepted VID/PID + `product_string=None` | candidate `product_string_status="unreadable"` | 実機 gate でのみ使用 |
| unsupported product string | accepted VID/PID + readable unknown string | rejected `unsupported_product_string` | 誤 device 防止 |
| descriptor retry | `getProduct()` が失敗し、language descriptor が読める | product string を補完 | vendor command は送らない |
| open matching | expected product string が unreadable | 再列挙時も unreadable の同一 VID/PID/location だけ open | 読めた別 product は拾わない |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | unreadable accepted VID/PID が candidate になる | unit | 3.1 | device filter |
| todo | readable unsupported product string が rejected になる | unit | 3.1 | safety |
| todo | descriptor retry が product string を補完する | unit | 3.1 | libusb backend fake |
| todo | open matching が unreadable expected で readable product を拒否する | unit | 3.1 | conservative matching |
| todo | metadata / stats / hardware plan が status を JSON 化する | unit | 3.1 | artifact traceability |
| deferred | 実機 listing が unreadable candidate を表示する | hardware | 3.1 | approval required |
| deferred | 実機 open/close が accepted VID/PID + unreadable で通る | hardware | 3.1 | approval required |

### 3.3 設計方針

Windows PnP / PowerShell subprocess は transport 層へ入れない。descriptor retry は libusb / usb1 の standard descriptor read に限定し、configuration 変更、interface claim、kernel driver detach、N3DSXL vendor command は行わない。

## 4. 実装仕様

```python
ProductStringStatus = Literal["accepted", "unreadable"]

@dataclass(frozen=True, slots=True)
class DeviceCandidate:
    info: UsbDeviceInfo
    product_string: AcceptedProductString | None
    product_string_status: ProductStringStatus
    model: Literal["new_3ds_xl"] = "new_3ds_xl"
```

`classify_n3dsxl_device()` は accepted VID/PID であれば `product_string=None` を candidate とする。`product_string` が存在し、accepted product string に含まれない場合は rejected とする。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| device filter | unreadable product string の candidate 化 | `0x0403:0x601e`, `None` | `DeviceCandidate` |
| libusb backend | descriptor retry | fake handle + lang id | `N3DSXL.2` |
| hardware gate | unreadable status の許可 | product `None` | allowed |
| metadata/stats | status の記録 | unreadable candidate | JSON 化可能 |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| listing | 実機を candidate として表示 | human approval | `product=- product_status=unreadable` または accepted product |
| open/close | interface claim/release | human approval, `PONKAN_RUN_N3DSXL=1` | 複数回成功 |

### 検証コマンド

```console
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

実機検証:

```console
$env:PONKAN_HARDWARE_APPROVED = "1"
uv run python -m py3dscapture.tools.list_devices

$env:PONKAN_RUN_N3DSXL = "1"
$env:PONKAN_HARDWARE_APPROVED = "1"
uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_open_close.py
```

## 6. 実装チェックリスト

- [x] 仕様と safety guide を product string status policy に更新する。
- [x] device filter と list CLI を更新する。
- [x] libusb descriptor retry と matching rule を更新する。
- [x] metadata / stats / hardware command plan を status 対応にする。
- [x] unit test を追加・更新する。
- [x] local gate を実行する。
- [x] 実機 listing gate を人間承認後に実行する。
- [ ] 実機 open-close gate を driver 状態調整後に再実行する。

## 7. Gate 結果

| Gate | 結果 | 証拠 |
| ---- | ---- | ---- |
| unit | pass | `uv run pytest tests/unit`: 63 passed |
| format | pass | `uv run ruff format --check .`: 53 files already formatted |
| lint | pass | `uv run ruff check .`: All checks passed |
| type | pass | `uv run ty check --no-progress`: All checks passed |
| e2e skip | pass | `uv run pytest tests/e2e`: 5 skipped |
| hardware listing | pass | `candidate bus=7 address=2 0x0403:0x601e product=- product_status=unreadable serial=-` |
| hardware open-close | blocked | `libusb_open` が `LIBUSB_ERROR_NOT_FOUND [-5]`。PnP service は `FTDIBUS3`。 |

hardware open-close の blocker は product string policy ではなく、Windows driver と libusb open path の不一致である。次の作業では WinUSB/libusbK driver へ切り替えて再検証するか、FTDI D3XX driver を使う backend を別 Work Unit として検討する。
