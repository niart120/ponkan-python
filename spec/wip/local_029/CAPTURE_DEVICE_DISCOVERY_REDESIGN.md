# Capture Device Discovery Redesign 仕様書

更新日: 2026-06-14

## 1. 概要

### 1.1 目的

profile 横断の `list_capture_devices()` を、既存の N3DSXL listing、D3XX descriptor enumeration、CLI listing を置き換える discovery contract として再設計する。利用側が複数台接続、device selection、accepted / rejected / unsupported device、product string unreadable、backend runtime 不足を文字列解析なしで扱えるようにする。

backend preference の解決と runtime 可用性は discovery の一部として扱い、別の public surface へ分けない。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| capture device info | public API が返す device descriptor と discovery 状態の正規化データ。 |
| device id | 利用側が設定に保存できる identifier。backend と serial / descriptor 情報から作る。 |
| backend preference | `auto`、`d3xx`、`d3xx-native`、`libusb` など、呼び出し側が希望する enumeration backend。 |
| resolved backend | discovery 実行時に実際に使った backend。 |
| connection status | `available`、`rejected`、`unsupported`、`unknown` の device visibility state。product string の読取結果は含めない。 |
| product string status | `accepted`、`unreadable`、`rejected` など、N3DSXL safety boundary の判断材料。 |
| discovery reason | device または backend を通常候補として扱えない理由を示す stable string。 |

### 1.3 背景・問題

現行 device discovery は `ponkan.devices.n3dsxl_ftd3.list_n3dsxl_devices()` と `D3xxBackend.iter_device_candidates()`、CLI listing に分散している。これらは N3DSXL の VID/PID、product string、descriptor の分類を既に持つ一方、public API として扱える stable device info、backend 可用性、rejected reason の責務境界が揃っていない。

NyX の初期実装は physical device selection を scope 外にして `open_capture()` の既定選択に委譲しているが、複数台接続や将来 profile を考えると、public stable identifier と structured device info が必要になる。backend state を別 API に分けると、discovery で使う backend policy と UI 表示用 state が重複しやすい。

この仕様では、既存 listing の薄い adapter ではなく、descriptor enumeration と public discovery model の責務を整理して置き換える。discovery は N3DSXL command を送らず、device open / connect / stream setup は `open_capture()` が担当する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| device selection | high-level open の既定選択のみ | `list_capture_devices()` で候補を表示できる |
| backend runtime | import error や backend 実装ごとの例外に分散 | discovery reason と remediation で扱える |
| rejected device | CLI 文字列や low-level 型依存 | structured reason を返す |
| safety boundary | product string unreadable の扱いが API ごとに散る | `product_string_status` に集約し、connection visibility と分ける |
| profile 追加 | profile ごとに別 API | 同じ discovery API で扱う |
| command scope | listing と open の境界が曖昧 | discovery は command 送信なし |

### 1.5 着手条件

- [ ] `local_028` の profile registry が利用可能である。
- [ ] 現行 `DeviceCandidate` / `RejectedDevice` / `DeviceListing` と `D3xxBackend.iter_device_candidates()` の責務を確認する。
- [ ] `src/ponkan/tools/list_devices.py` の出力を public discovery model へ寄せる方針を決める。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_029/CAPTURE_DEVICE_DISCOVERY_REDESIGN.md` | 新規 | backend resolution を含む device discovery redesign を定義する。 |
| `src/ponkan/devices/discovery.py` | 新規 | `CaptureDeviceInfo`、discovery reason、backend preference 解決を定義する。 |
| `src/ponkan/devices/n3dsxl_ftd3.py` | 修正 | N3DSXL 固有の descriptor classification を shared discovery model へ接続し、session/open 責務を分離する。 |
| `src/ponkan/transport/d3xx_backend.py` | 修正 | D3XX descriptor enumeration を discovery から再利用できる境界へ整理する。 |
| `src/ponkan/tools/list_devices.py` | 修正 | CLI listing を public discovery model の表示に変更する。 |
| `src/ponkan/__init__.py` | 修正 | `list_capture_devices` と `CaptureDeviceInfo` を export する。 |
| `docs/api.md` | 修正 | device discovery の safety boundary、backend reason、利用例を追加する。 |
| `tests/unit/test_capture_device_discovery.py` | 新規 | fake backend で backend reason、accepted、rejected、unreadable を検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| N3DSXL を列挙する | `list_capture_devices(profile="n3dsxl")` | accepted devices を返す | command 送信なし |
| backend auto | `backend="auto"` | high-level open と同じ既定 backend policy で discovery する | policy drift を避ける |
| backend package 不足 | PyD3XX が import できない | device なし、または diagnostics info と `reason="missing_package"` | open しない |
| backend driver 不足 | D3XX runtime / driver が使えない | `reason="missing_driver"` または `reason="missing_runtime"` | remediation 付き |
| unsupported backend | profile に対して backend が未対応 | `reason="unsupported_backend"` | source audit 前に暗黙対応しない |
| rejected を含める | `include_rejected=True` | unsupported PID/product string も reason 付きで返す | diagnostics 用 |
| unreadable product string | accepted VID/PID で product unreadable | `connection_status="available"`, `product_string_status="unreadable"` | open は別途 safety boundary |
| device id を作る | serial あり | `d3xx:<serial>` など backend prefix 付き ID | stability best effort |
| serial なし | descriptor のみ | backend / bus / address などで一時 ID | stable でないことを metadata に出す |
| unknown profile | `profile="classic_ds"` | profile registry の error | source audit 前に暗黙対応しない |
| open しない | discovery API 呼び出し | N3DSXL connect / stream setup は実行しない | safety boundary |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | `backend="auto"` は high-level open と同じ既定 backend policy を使う | contract | 3.1 | policy drift 防止 |
| todo | PyD3XX missing が `reason="missing_package"` になる | diagnostics | 3.1 | import monkeypatch |
| todo | accepted N3DSXL candidate が `CaptureDeviceInfo` になる | new behavior | 3.1 | fake descriptor |
| todo | rejected product string が reason 付き info になる | diagnostics | 3.1 | include_rejected |
| todo | product string unreadable が product status として残る | safety | 3.1 | connection status には混ぜない |
| todo | device id が backend prefix を持つ | contract | 3.1 | `d3xx:` / `libusb:` |
| todo | discovery は command を送らない | safety | 3.1 | fake protocol spy |
| todo | CLI listing は public discovery model を表示する | integration | 3.1 | duplicate classification 防止 |
| todo | unknown profile は error | edge | 3.1 | typo 検知 |

### 3.3 設計方針

discovery API は「接続候補を表示するための metadata」を返す。device を open して capture できることを保証しない。実際の open / connect / command sequence は `open_capture()` が既存 safety boundary の中で行う。

backend selection は discovery の入力条件であり、別個の backend state registry にはしない。`auto` の解決、backend dependency、driver/runtime 不足は `CaptureDeviceInfo.reason` または空結果の structured error として表す。

device id は設定保存に使えるようにするが、serial が読めない環境では一時 ID になる。`id_stability` を metadata に持たせ、利用側が permanent / session の違いを判断できるようにする。

## 4. 実装仕様

```python
from dataclasses import dataclass
from typing import Literal

BackendPreference = Literal["auto", "d3xx", "d3xx-native", "libusb"]
ConnectionStatus = Literal["available", "rejected", "unsupported", "unknown"]
DiscoveryReason = Literal[
    "available",
    "missing_package",
    "missing_driver",
    "missing_runtime",
    "unsupported_platform",
    "unsupported_backend",
    "unsupported_profile",
    "device_rejected",
    "unknown",
]
IdStability = Literal["stable", "session", "unknown"]
ProductStringStatus = Literal["accepted", "unreadable", "rejected", "unknown"]


@dataclass(frozen=True, slots=True)
class CaptureDeviceInfo:
    id: str
    display_name: str
    profile_id: str
    model: str
    backend: str
    backend_preference: BackendPreference
    vendor_id: int | None
    product_id: int | None
    serial_number: str | None
    product_string: str | None
    product_string_status: ProductStringStatus
    connection_status: ConnectionStatus
    id_stability: IdStability
    reason: DiscoveryReason = "available"
    remediation: str | None = None
```

Public API:

```python
def list_capture_devices(
    *,
    profile: str = "n3dsxl",
    backend: BackendPreference = "auto",
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
| accepted candidate | `connection_status="available"`, `reason="available"` |
| `RejectedDevice.reason` | `reason="device_rejected"` または詳細 reason |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| backend auto | policy resolution | default | high-level open と同じ backend |
| backend missing | PyD3XX import missing | fake import error | `reason="missing_package"` |
| accepted mapping | descriptor to info | accepted VID/PID/string | `available` |
| unreadable mapping | product string None | accepted VID/PID | `connection_status="available"`, `product_string_status="unreadable"` |
| rejected mapping | unsupported PID | include_rejected | `device_rejected` reason |
| id generation | serial present | `nxl530228` | stable `d3xx:nxl530228` |
| safety | no command | fake backend | connect / stream は呼ばれない |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| CLI parity | public API と existing CLI listing の情報整合 | 実機なし fake | accepted/rejected が一致 |
| hardware listing | 実機 descriptor listing | 実機、command 承認不要 | command 送信なしで候補を列挙 |

### 検証コマンド

```console
uv run pytest tests/unit/test_capture_device_discovery.py
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

Hardware listing は N3DSXL command を送らないが、実機に触れるため計画と artifact を明示してから実行する。

## 6. 実装チェックリスト

- [ ] `CaptureDeviceInfo` と discovery reason を定義する。
- [ ] backend preference 解決を discovery に統合する。
- [ ] N3DSXL `DeviceListing` から public info への mapping を実装する。
- [ ] CLI listing を public discovery model へ寄せる。
- [ ] rejected / unreadable / id stability / backend reason を unit test で固定する。
- [ ] docs/api に discovery の command scope と backend reason を明記する。
- [ ] local gate を実行する。
