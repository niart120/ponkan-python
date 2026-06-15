# Capture Device Discovery Redesign 仕様書

更新日: 2026-06-15

## 1. 概要

### 1.1 目的

profile 横断の `list_capture_devices()` を、既存の N3DSXL listing、D3XX descriptor enumeration、CLI listing を置き換える discovery contract として再設計する。利用側が複数台接続、device selection、accepted / rejected / unsupported device、product string unreadable、backend runtime 不足を文字列解析なしで扱えるようにする。

backend preference の解決と runtime 可用性は discovery の一部として扱い、別の public surface へ分けない。backend 不足や未接続状態も例外・空 tuple・疑似 device に分散せず、単一の discovery result object で返す。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| capture device info | public API が返す device descriptor と discovery 状態の正規化データ。 |
| device id | 利用側が設定に保存できる identifier。backend と serial / descriptor 情報から作る。 |
| backend preference | `auto`、`d3xx`、`d3xx-native`、`libusb` など、呼び出し側が希望する enumeration backend。 |
| resolved backend | discovery 実行時に実際に使った backend。 |
| discovery result | backend state と device list をまとめて返す public object。 |
| backend status | `available`、`unavailable`、`unsupported` の backend 可用性。 |
| connection status | `available`、`rejected`、`unsupported`、`unknown` の device visibility state。product string の読取結果は含めない。 |
| product string status | `accepted`、`unreadable`、`rejected` など、N3DSXL safety boundary の判断材料。 |
| capture reason | device または backend を通常候補として扱えない理由を示す stable string。`local_030` の error reason と同じ enum を使う。 |

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

- [x] `local_028` の profile registry が利用可能である。
- [x] `local_030` の `CaptureReason` が利用可能である。
- [x] 現行 `DeviceCandidate` / `RejectedDevice` / `DeviceListing` と `D3xxBackend.iter_device_candidates()` の責務を確認する。
- [x] `src/ponkan/tools/list_devices.py` の出力を public discovery model へ寄せる方針を決める。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/complete/local_029/CAPTURE_DEVICE_DISCOVERY_REDESIGN.md` | 完了済み | backend resolution を含む device discovery redesign を定義する。 |
| `src/ponkan/devices/discovery.py` | 新規 | `CaptureDeviceInfo`、discovery reason、backend preference 解決を定義する。 |
| `src/ponkan/devices/n3dsxl_ftd3.py` | 既存利用 | N3DSXL 固有の descriptor classification を discovery adapter から再利用する。 |
| `src/ponkan/transport/d3xx_backend.py` | 既存利用 | `iter_devices()` の descriptor enumeration を discovery から再利用する。 |
| `src/ponkan/capture.py` | 修正 | `backend="auto"` の resolver を discovery / high-level open で共有し、Windows では `d3xx-native` を既定にする。 |
| `src/ponkan/tools/list_devices.py` | 修正 | CLI listing を public discovery model の表示に変更する。 |
| `src/ponkan/__init__.py` | 修正 | `list_capture_devices`、`CaptureDeviceDiscovery`、`CaptureDeviceInfo` を export する。 |
| `docs/api.md` | 修正 | device discovery の safety boundary、backend reason、利用例を追加する。 |
| `tests/unit/test_capture_device_discovery.py` | 新規 | fake backend で backend reason、accepted、rejected、unreadable を検証する。 |
| `tests/unit/test_high_level_capture_read_api.py` | 修正 | high-level `backend="auto"` が Windows で `d3xx-native` に解決され、`d3xx` へ silent fallback しないことを検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| N3DSXL を列挙する | `list_capture_devices(profile="n3dsxl")` | `backend_status="available"` で accepted devices を `devices` に返す | command 送信なし |
| backend auto | `backend="auto"` | OS / backend policy に従う `resolved_backend` を返す | policy drift を避ける |
| Windows default | `sys_platform == "win32"`, `backend="auto"` | `resolved_backend="d3xx-native"` | D3XX sequential path の画面不安定観測を受けた Intent Delta |
| native dependency unavailable | Windows auto で PyD3XX dependency が利用不可 | `backend_status="unavailable"`, `reason="missing_package"` の result を返す | `d3xx` へ silent fallback しない |
| backend package 不足 | PyD3XX が import できない | `backend_status="unavailable"`, `reason="missing_package"` の result を返す | open しない |
| D3XX API failure | descriptor enumeration 中に D3XX binding call / detail parse が失敗 | `D3xxBackendError` などの `CaptureError` を送出する | `function` / `status` / `field_name` を technical log に使う |
| unsupported backend | profile に対して backend が未対応 | `backend_status="unsupported"`, `reason="unsupported_backend"` | source audit 前に暗黙対応しない |
| device 未接続 | backend は使えるが候補なし | `backend_status="available"`, `reason="device_not_found"`, `devices=()` | UI は source を表示し未接続 status にできる |
| rejected を含める | `include_rejected=True` | unsupported PID/product string も device info と reason 付きで `devices` に返す | diagnostics 用 |
| unreadable product string | accepted VID/PID で product unreadable | `connection_status="available"`, `product_string_status="unreadable"` | open は別途 safety boundary |
| device id を作る | serial あり | `d3xx:<serial>` など backend prefix 付き ID | stability best effort |
| serial なし | descriptor のみ | backend / bus / address などで一時 ID | stable でないことを metadata に出す |
| unknown profile | `profile="classic_ds"` | `backend_status="unsupported"`, `reason="unsupported_profile"` の result を返す | source audit 前に暗黙対応しない |
| open しない | discovery API 呼び出し | N3DSXL connect / stream setup は実行しない | safety boundary |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | `backend="auto"` は high-level open と同じ既定 backend policy を使う | contract | 3.1 | policy drift 防止 |
| green | Windows auto は `d3xx-native` に解決される | behavior | 3.1 | D3XX sequential path の不安定観測に基づく |
| green | Windows auto は native unavailable 時に `d3xx` へ silent fallback しない | safety | 3.1 | 明示指定のみ許可 |
| green | PyD3XX missing が `reason="missing_package"` になる | diagnostics | 3.1 | import monkeypatch |
| green | backend dependency 不足時も single discovery result object で返る | contract | 3.1 | PyD3XX import failure を空 tuple / 疑似 device にしない |
| green | accepted N3DSXL candidate が `CaptureDeviceInfo` になる | new behavior | 3.1 | fake descriptor |
| green | rejected product string が reason 付き info になる | diagnostics | 3.1 | include_rejected |
| green | product string unreadable が product status として残る | safety | 3.1 | connection status には混ぜない |
| green | device id が backend prefix を持つ | contract | 3.1 | `d3xx:` / `libusb:` |
| green | discovery は command を送らない | safety | 3.1 | fake protocol spy |
| green | CLI listing は libusb descriptor path の public discovery model を表示する | integration | 3.1 | duplicate classification 防止 |
| green | unknown profile は unsupported result object を返す | edge | 3.1 | typo 検知 |

### 3.3 設計方針

discovery API は「接続候補を表示するための metadata」を返す。device を open して capture できることを保証しない。実際の open / connect / command sequence は `open_capture()` が既存 safety boundary の中で行う。

backend selection は discovery の入力条件であり、別個の backend state registry にはしない。`auto` の解決、backend dependency 不足、device 未接続は `CaptureDeviceDiscovery` の `backend_status` / `reason` / `remediation` として表す。PyD3XX import failure は空 tuple や疑似 device にせず、backend-level unavailable result として返す。一方、D3XX API call failure や descriptor detail の unsupported shape は `D3xxBackendError` として送出し、呼び出し側の technical log が `function` / `status` / `field_name` を使えるようにする。

`backend="auto"` の初期 resolver は OS / backend policy を共有する。Windows では `d3xx-native` を既定とし、D3XX sequential backend は `backend="d3xx"` の明示指定時だけ使う。これは `local_021` / `local_022` の過去測定では native default 化を見送った判断を、後続の「D3XX sequential path では画面が不安定になる」という観測で再評価する Intent Delta とする。native dependency が unavailable の場合に `d3xx` へ silent fallback すると不安定 path へ戻るため、discovery は unavailable reason を返し、high-level open は structured error を送出する。

device id は設定保存に使えるようにするが、serial が読めない環境では一時 ID になる。`id_stability` を metadata に持たせ、利用側が permanent / session の違いを判断できるようにする。

## 4. 実装仕様

```python
from dataclasses import dataclass
from typing import Literal

from ponkan.errors import CaptureReason

BackendPreference = Literal["auto", "d3xx", "d3xx-native", "libusb"]
BackendStatus = Literal["available", "unavailable", "unsupported"]
ConnectionStatus = Literal["available", "rejected", "unsupported", "unknown"]
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
    reason: CaptureReason = "available"
    remediation: str | None = None


@dataclass(frozen=True, slots=True)
class CaptureDeviceDiscovery:
    profile_id: str
    backend_preference: BackendPreference
    resolved_backend: str
    backend_status: BackendStatus
    reason: CaptureReason = "available"
    remediation: str | None = None
    devices: tuple[CaptureDeviceInfo, ...] = ()
```

Public API:

```python
def list_capture_devices(
    *,
    profile: str = "n3dsxl",
    backend: BackendPreference = "auto",
    include_rejected: bool = False,
) -> CaptureDeviceDiscovery:
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
| `RejectedDevice.reason` | `reason="device_rejected"`、詳細は `remediation` または future detail field |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| backend auto | policy resolution | default | high-level open と同じ backend |
| Windows native default | policy resolution | Windows auto | `resolved_backend == "d3xx-native"` |
| native fallback guard | PyD3XX missing | Windows auto | `d3xx` へ silent fallback せず unavailable result |
| backend missing | PyD3XX import missing | fake import error | `reason="missing_package"` |
| accepted mapping | descriptor to info | accepted VID/PID/string | `available` |
| unreadable mapping | product string None | accepted VID/PID | `connection_status="available"`, `product_string_status="unreadable"` |
| rejected mapping | unsupported PID | include_rejected | `device_rejected` reason |
| id generation | serial present | `nxl530228` | stable `d3xx:nxl530228` |
| safety | no command | fake backend | connect / stream は呼ばれない |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| CLI parity | libusb descriptor CLI と public discovery model の情報整合 | 実機なし fake | `backend="libusb"` result と accepted/rejected が一致し、resolved backend を表示する |
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

- [x] `CaptureDeviceInfo` と discovery reason を定義する。
- [x] backend preference 解決を discovery に統合する。
- [x] Windows の `backend="auto"` を `d3xx-native` に解決し、`d3xx` へ silent fallback しない。
- [x] N3DSXL `DeviceListing` から public info への mapping を実装する。
- [x] CLI listing を libusb descriptor path の public discovery model へ寄せる。
- [x] rejected / unreadable / id stability / backend reason を unit test で固定する。
- [x] docs/api に discovery の command scope と backend reason を明記する。
- [x] local gate を実行する。

## 7. 実装結果

### 7.1 Gate Results

| gate | result | evidence |
| ---- | ------ | -------- |
| Discovery unit | pass | `uv run pytest tests/unit/test_capture_device_discovery.py -q`: 6 passed。 |
| Related unit | pass | `uv run pytest tests/unit/test_capture_device_discovery.py tests/unit/test_n3dsxl_list_devices_cli.py tests/unit/test_high_level_capture_read_api.py tests/unit/test_package.py -q`: 28 passed。 |
| Full unit | pass | `uv run pytest tests/unit`: 146 passed。 |
| Static | pass | `uv run ruff format --check .`、`uv run ruff check .`、`uv run ty check --no-progress`。 |
| Diff | pass | `git diff --check`。 |
| Hardware listing | not run | Discovery は command を送らないが、実機接続状態に触れるため PR 後の任意 gate とする。 |

### 7.2 Deferred

実機 descriptor listing は command 送信を伴わないが、今回の PR は fake backend による contract 固定までとした。現行 `ponkan-list-devices` は libusb descriptor path の diagnostic CLI として扱う。`backend="auto"` / D3XX native の discovery smoke は、必要な device identity と artifact 方針を示した上で別途実行する。
