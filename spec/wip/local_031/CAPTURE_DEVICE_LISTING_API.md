# Capture Device Listing API 仕様書

更新日: 2026-06-14

## 1. 概要

### 1.1 目的

profile 横断の `list_capture_devices()` を追加し、利用側が複数台接続、device selection、accepted / rejected / unsupported / unreadable product string の判定を文字列解析なしで扱えるようにする。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| capture device info | public API が返す device descriptor の正規化データ。 |
| device id | 利用側が設定に保存できる stable identifier。backend と serial / descriptor 情報から作る。 |
| connection status | `available`、`rejected`、`unsupported`、`unreadable` などの device state。 |
| product string status | `accepted`、`unreadable`、`rejected` など、N3DSXL safety boundary の判断材料。 |

### 1.3 背景・問題

現行 device discovery は `ponkan.devices.n3dsxl_ftd3.list_n3dsxl_devices()` と CLI を持つが、profile 横断の public listing API はない。NyX の初期実装は physical device selection を scope 外にして `open_capture()` の既定選択に委譲しているが、複数台接続や将来 profile を考えると、public stable identifier と structured device info が必要になる。

この仕様では、listing は N3DSXL command を送らない。descriptor classification と backend enumeration までを扱う。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| device selection | high-level open の既定選択のみ | `list_capture_devices()` で候補を表示できる |
| rejected device | CLI 文字列や low-level 型依存 | structured reason を返す |
| safety boundary | product string unreadable の扱いが API ごとに散る | `product_string_status` と `connection_status` に集約 |
| profile 追加 | profile ごとに別 API | 同じ listing API で扱う |
| command scope | listing と open の境界が曖昧 | listing は command 送信なし |

### 1.5 着手条件

- [ ] `local_027` の profile registry が利用可能である。
- [ ] `local_028` の backend resolver が利用可能である。
- [ ] 現行 `DeviceCandidate` / `RejectedDevice` / `DeviceListing` の情報を public info に変換できる。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_031/CAPTURE_DEVICE_LISTING_API.md` | 新規 | profile 横断 listing API の仕様を定義する。 |
| `src/ponkan/devices/base.py` | 新規 | `CaptureDeviceInfo` と共通 listing 型を定義する。 |
| `src/ponkan/devices/n3dsxl_ftd3.py` | 修正 | N3DSXL listing を public info に変換する adapter を追加する。 |
| `src/ponkan/capture.py` | 修正 | `device_id` 指定 open を後続で接続できるように config field を検討する。 |
| `src/ponkan/__init__.py` | 修正 | `list_capture_devices` と `CaptureDeviceInfo` を export する。 |
| `docs/api.md` | 修正 | device listing の safety boundary と例を追加する。 |
| `tests/unit/test_capture_device_listing_api.py` | 新規 | fake backend で accepted / rejected / unreadable を検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| N3DSXL を列挙する | `list_capture_devices(profile="n3dsxl")` | accepted devices を返す | command 送信なし |
| rejected を含める | `include_rejected=True` | unsupported PID/product string も reason 付きで返す | diagnostics 用 |
| unreadable product string | accepted VID/PID で product unreadable | `product_string_status="unreadable"` | open は別途 safety boundary |
| device id を作る | serial あり | `d3xx:<serial>` など backend prefix 付き ID | stability best effort |
| serial なし | descriptor のみ | backend / bus / address などで一時 ID | stable でないことを metadata に出す |
| backend auto | `backend="auto"` | resolver と一致する listing backend を使う | `local_028` と整合 |
| unknown profile | `profile="classic_ds"` | profile registry の error | source audit 前に暗黙対応しない |
| open しない | listing API 呼び出し | N3DSXL connect / stream setup は実行しない | safety boundary |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | accepted N3DSXL candidate が `CaptureDeviceInfo` になる | new behavior | 3.1 | fake descriptor |
| todo | rejected product string が reason 付き info になる | diagnostics | 3.1 | include_rejected |
| todo | product string unreadable が status として残る | safety | 3.1 | open ではない |
| todo | device id が backend prefix を持つ | contract | 3.1 | `d3xx:` / `libusb:` |
| todo | listing は command を送らない | safety | 3.1 | fake protocol spy |
| todo | unknown profile は error | edge | 3.1 | typo 検知 |

### 3.3 設計方針

listing API は「接続候補を表示するための metadata」を返す。device を open して capture できることを保証しない。実際の open / connect / command sequence は `open_capture()` が既存 safety boundary の中で行う。

device id は設定保存に使えるようにするが、serial が読めない環境では一時 ID になる。`id_stability` を metadata に持たせ、利用側が permanent / session の違いを判断できるようにする。

## 4. 実装仕様

```python
from dataclasses import dataclass
from typing import Literal

ConnectionStatus = Literal["available", "rejected", "unsupported", "unknown"]
IdStability = Literal["stable", "session", "unknown"]


@dataclass(frozen=True, slots=True)
class CaptureDeviceInfo:
    id: str
    display_name: str
    profile_id: str
    model: str
    backend: str
    vendor_id: int | None
    product_id: int | None
    serial_number: str | None
    product_string: str | None
    product_string_status: str | None
    connection_status: ConnectionStatus
    id_stability: IdStability
    reason: str | None = None
```

Public API:

```python
def list_capture_devices(
    *,
    profile: str = "n3dsxl",
    backend: str = "auto",
    include_rejected: bool = False,
) -> tuple[CaptureDeviceInfo, ...]:
    ...
```

N3DSXL 初期 mapping:

| source | public field |
| ------ | ------------ |
| `DeviceCandidate.info.vendor_id` | `vendor_id` |
| `DeviceCandidate.info.product_id` | `product_id` |
| `DeviceCandidate.info.serial_number` | `serial_number` |
| `DeviceCandidate.product_string_status` | `product_string_status` |
| accepted candidate | `connection_status="available"` |
| `RejectedDevice.reason` | `reason` |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| accepted mapping | descriptor to info | accepted VID/PID/string | `available` |
| unreadable mapping | product string None | accepted VID/PID | `product_string_status="unreadable"` |
| rejected mapping | unsupported PID | include_rejected | `rejected` reason |
| id generation | serial present | `nxl530228` | stable `d3xx:nxl530228` |
| safety | no command | fake backend | connect / stream は呼ばれない |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| CLI parity | public API と existing CLI listing の情報整合 | 実機なし fake | accepted/rejected が一致 |
| hardware listing | 実機 descriptor listing | 実機、command 承認不要 | command 送信なしで候補を列挙 |

### 検証コマンド

```console
uv run pytest tests/unit/test_capture_device_listing_api.py
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

Hardware listing は N3DSXL command を送らないが、実機に触れるため計画と artifact を明示してから実行する。

## 6. 実装チェックリスト

- [ ] `CaptureDeviceInfo` を定義する。
- [ ] N3DSXL `DeviceListing` から public info への adapter を実装する。
- [ ] `list_capture_devices()` を profile / backend resolver と接続する。
- [ ] rejected / unreadable / id stability を unit test で固定する。
- [ ] docs/api に listing の command scope を明記する。
- [ ] local gate を実行する。
