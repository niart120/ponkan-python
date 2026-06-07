# N3DSXL Device Discovery And Session 仕様書

更新日: 2026-06-07

## 1. 概要

### 1.1 目的

Step 1-2 として、libusb backend から new 3DS XL capture board を安全に列挙し、対象 device を open / claim / close できる session layer を実装する。

未知の FTDI device へ N3DSXL command を送らないため、この Work Unit は product string の確認を必須 gate とする。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| Device Candidate | VID/PID/product string が N3DSXL 条件を満たす USB device。 |
| Rejected Device | VID/PID は近いが product string 不一致、または product string を確認できない device。 |
| Libusb Backend | device enumeration、open、configuration、claim/release、close を担当する薄い wrapper。 |
| N3DSXL Session | open 済み handle と claimed interface を所有する object。 |
| Safe Open | product string を確認した candidate にだけ open/claim を進める処理。 |

### 1.3 背景・問題

new 3DS XL capture board は FTDI VID を使うが、FTDI VID だけでは対象 device と判断できない。product string が `N3DSXL` / `N3DSXL.2` でない device に command を送らないため、listing と session 作成を protocol 実行より前に分ける必要がある。

`spec/initial` では Step 1 が device listing、Step 2 が open / claim / close である。Agentic SDD では、Step 1 の mock unit test と CLI を先に実装し、実機 E2E は人間承認後に扱う。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| device 誤認 | 実装なし | VID/PID/product string の三条件で candidate 化する |
| 実機前検証 | 実装なし | fake libusb backend で listing / filtering を単体テストする |
| cleanup | 実装なし | open 失敗、claim 失敗、例外、Ctrl-C で release/close を保証する |
| CLI bring-up | 実装なし | `tools/list_devices.py` で候補と拒否理由を表示する |

### 1.5 着手条件

- [x] `spec/complete/local_009/N3DSXL_DEVICE_IDENTITY_AND_SIZES.md` の identity constants が存在する。
- [x] libusb binding の薄い wrapper 方針を決める。
- [ ] 実機 E2E を実行する場合、new 3DS XL capture board の接続と人間承認がある。

### 1.6 Work Unit メタデータ

| 項目 | 内容 |
| ---- | ---- |
| 配置 | `spec/complete/local_010/N3DSXL_DEVICE_DISCOVERY_AND_SESSION.md` |
| 対応 Step | Step 1: device listing、Step 2: open / claim / close |
| 前提 Work Unit | `spec/complete/local_009/N3DSXL_DEVICE_IDENTITY_AND_SIZES.md` |
| 次 Work Unit | `spec/wip/local_011/N3DSXL_FTD3_PIPE_AND_CONNECT.md` |
| local task | fake backend、device classifier、session cleanup、CLI 表示。 |
| hardware task | 実機 listing と open/claim/close E2E。 |
| 選択条件 | Step 0 が通過し、N3DSXL command を送る前の device guard / session ownership が未実装のとき。 |
| 完了証拠 | fake backend の unit test が通り、実機 gate は承認待ちまたは実行結果つきで報告されている。 |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `src/py3dscapture/transport/libusb_backend.py` | 新規 | libusb device enumeration と session primitive を薄く包む。 |
| `src/py3dscapture/devices/n3dsxl_ftd3.py` | 新規 | N3DSXL candidate filtering、open/claim/close を実装する。 |
| `src/py3dscapture/errors.py` | 新規 | device/session 系例外を定義する。 |
| `src/py3dscapture/tools/list_devices.py` | 新規 | device listing CLI を提供する。 |
| `tests/unit/test_n3dsxl_device_filter.py` | 新規 | fake device で filtering を検証する。 |
| `tests/unit/test_n3dsxl_session.py` | 新規 | fake backend で open/claim/close cleanup を検証する。 |
| `tests/unit/test_n3dsxl_list_devices_cli.py` | 新規 | fake backend で listing と rejected reason 表示を検証する。 |
| `tests/e2e/test_n3dsxl_open_close.py` | 新規 | 実機 open/claim/close を検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| candidate を列挙する | backend が USB device 群を返す | VID `0x0403`、accepted PID、product string accepted の device だけ candidate にする | product string は必須 |
| rejected device を説明する | FTDI VID だが条件不一致 | `rejected_reason` に PID 不一致、product string 不一致、product string unreadable などを残す | CLI 表示用 |
| product string unreadable を拒否する | string descriptor read が失敗する | N3DSXL candidate にしない | 安全側 |
| list CLI を実行する | `uv run python -m py3dscapture.tools.list_devices` | candidate と rejected summary を表示する | 実機 command ではなく列挙。command pipe は送らない |
| safe open する | Device Candidate を渡す | configuration 1、interface 0/1 claim が完了する | command はまだ送らない |
| unknown device open を拒否する | Candidate でない device を渡す | `UnsupportedDevice` を送出する | N3DSXL command を送らない |
| close を冪等にする | close を複数回呼ぶ | 例外なく、claimed interface と handle を解放する | 例外中 cleanup も同じ |
| claim 途中失敗を cleanup する | interface 0 claim 後、interface 1 claim 失敗 | interface 0 release と handle close を実行する | fake backend で検証 |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | accepted VID/PID/product string の fake device だけ candidate になる | new behavior | 3.1 | `tests/unit/test_n3dsxl_device_filter.py` |
| green | product string が `N3DSXL.2` でも candidate になる | new behavior | 3.1 | variant |
| green | accepted PID でも product string 不一致なら rejected になる | safety | 3.1 | 誤 device 防止 |
| green | product string unreadable なら rejected になる | safety | 3.1 | 安全側 |
| green | open は configuration 1 と interface 0/1 claim を順に呼ぶ | new behavior | 3.1 | fake backend |
| green | interface 1 claim 失敗時に interface 0 release と handle close が呼ばれる | regression | 3.1 | cleanup |
| green | close は冪等で複数回呼んでも安全 | regression | 3.1 | cleanup |
| green | list_devices CLI が candidate と rejected reason を表示する | new behavior | 3.1 | stdout snapshot は過度に固定しない |
| deferred | 実機 open -> claim -> close が複数回成功する | hardware | 3.1 | `requires_n3dsxl`。人間承認待ち |

### 3.3 設計方針

libusb wrapper は thin wrapper に留め、N3DSXL protocol logic を混ぜない。product string filtering は device layer に置き、FTD3 pipe は session 作成後の別 Work Unit にする。

Backend protocol は fake 実装を差し替えやすくする。

```python
class LibusbBackend(Protocol):
    def iter_devices(self) -> Iterable[UsbDeviceInfo]: ...
    def open(self, device: UsbDeviceInfo) -> UsbHandle: ...
```

`N3DSXLDevice` は claimed interface の所有権を持ち、context manager で使えるようにする。

```python
with N3DSXLDevice.open(candidate, backend=backend) as device:
    ...
```

Source Audit:

| 項目 | 状態 | 必要 action |
| ---- | ---- | ----------- |
| VID/PID/product string/interface/endpoint | `local_009` で初期仕様由来として固定 | 変更時のみ source audit |
| libusb setup order | `cc3dsfs` 原典 `source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_libusb_comms.cpp` で確認 | detach kernel driver、configuration 1、command interface 0 claim、bulk interface 1 claim の順序を local 実装へ反映。control IN probe と create command は `local_011` へ送る |
| control IN probe | Step 4 へ送る | この Work Unit では command を送らない |

Hardware:

| 項目 | 扱い |
| ---- | ---- |
| listing CLI | USB descriptor read だけ。実機 command ではないが、実機接続を使う場合は結果を報告する。 |
| open/claim/close E2E | `@pytest.mark.requires_n3dsxl`。人間承認後に `PONKAN_RUN_N3DSXL=1` と実行する。 |
| N3DSXL command | この Work Unit では送らない。 |

### 3.4 Agentic SDD Task Graph

| 分類 | Task | Gate |
| ---- | ---- | ---- |
| Blocking local task | `UsbDeviceInfo`、`DeviceCandidate`、`RejectedDevice` を定義する | 型チェック、classifier unit test |
| Blocking local task | fake backend で classifier と rejected reason を TDD 実装する | `tests/unit/test_n3dsxl_device_filter.py` |
| Blocking local task | session open/close ownership と cleanup を fake backend で実装する | `tests/unit/test_n3dsxl_session.py` |
| Sidecar task | libusb binding の enumeration API と product string read の仕様確認 | source/doc note |
| Hardware task | 実機 listing と open/claim/close | human approval、`requires_n3dsxl` |

`local_010` では FTD3 command pipe、control probe、stream setup、raw capture を実装しない。control IN probe は `local_011` の connect work に送る。

## 4. 実装仕様

### 4.1 Data Types

```python
@dataclass(frozen=True, slots=True)
class UsbDeviceInfo:
    bus_number: int | None
    address: int | None
    vendor_id: int
    product_id: int
    product_string: str | None
    serial_number: str | None = None

@dataclass(frozen=True, slots=True)
class DeviceCandidate:
    info: UsbDeviceInfo
    model: Literal["new_3ds_xl"] = "new_3ds_xl"
    product_string: Literal["N3DSXL", "N3DSXL.2"]

@dataclass(frozen=True, slots=True)
class RejectedDevice:
    info: UsbDeviceInfo
    reason: str
```

### 4.2 Filtering

```python
def classify_n3dsxl_device(info: UsbDeviceInfo) -> DeviceCandidate | RejectedDevice | None:
    if info.vendor_id != N3DSXL_VENDOR_ID:
        return None
    if info.product_id not in ACCEPTED_N3DSXL_PRODUCT_IDS:
        return RejectedDevice(info, "unsupported_product_id")
    if info.product_string is None:
        return RejectedDevice(info, "product_string_unreadable")
    if info.product_string not in ACCEPTED_N3DSXL_PRODUCT_STRINGS:
        return RejectedDevice(info, "unsupported_product_string")
    return DeviceCandidate(info=info, product_string=cast(...))
```

Non-FTDI device は rejected summary に出してもよいが、CLI の既定では候補と FTDI rejected だけを表示する。

### 4.3 Session

```python
class N3DSXLDevice:
    @classmethod
    def open(cls, candidate: DeviceCandidate, backend: LibusbBackend | None = None) -> N3DSXLDevice:
        ...

    def close(self) -> None:
        ...

    def __enter__(self) -> N3DSXLDevice:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
```

open sequence:

```text
1. candidate であることを確認する。
2. backend.open(candidate.info) で handle を得る。
3. 必要なら kernel driver detach を interface 0/1 に行う。
4. set_configuration(1) を行う。
5. claim_interface(0) を行う。
6. claim_interface(1) を行う。
7. session object を返す。
```

failure cleanup:

```text
- interface 1 claim 失敗: interface 0 release -> handle close
- configuration 失敗: handle close
- close 中の release 失敗: handle close は続行し、最後に close error を記録する
```

### 4.4 完了判定

この仕様の local completion は、実機なしでも成立する。ただし hardware completion は別 gate として残す。

| 判定 | 必須 evidence |
| ---- | ------------- |
| local complete | classifier unit test、session cleanup unit test、CLI import test、ruff/ty が通る |
| hardware pending | 実機 command scope と承認待ち理由を gate 報告に残す |
| hardware complete | `requires_n3dsxl` の open/close E2E 結果、VID/PID/product string、cleanup 結果を残す |

実装結果:

| 項目 | Evidence |
| ---- | -------- |
| local complete | `uv run pytest tests\unit\test_n3dsxl_device_filter.py tests\unit\test_n3dsxl_session.py tests\unit\test_n3dsxl_list_devices_cli.py -q` が 11 passed |
| unit regression | `uv run pytest tests\unit -q` が 16 passed |
| static | `uv run ruff check src tests` と `uv run ty check --no-progress` が pass |
| hardware pending | `uv run pytest tests\e2e\test_n3dsxl_open_close.py -q` は `PONKAN_RUN_N3DSXL` 未設定で skip。実機 command は未実行 |
| source audit | `3dscapture_ftd3_libusb_comms.cpp` の libusb setup と `3dscapture_ftd3_shared.cpp` の accepted product string を確認 |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| classifier | accepted device | `0x0403:0x601f`, `N3DSXL` | `DeviceCandidate` |
| classifier | product string mismatch | `0x0403:0x601f`, `FT232H` | `RejectedDevice("unsupported_product_string")` |
| classifier | unreadable product string | `product_string=None` | rejected |
| session open | call order | fake backend | configuration and claim 0/1 |
| session cleanup | interface 1 failure | fake backend raises | release 0 and close |
| close | idempotency | close twice | no extra unsafe calls |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| list CLI | 実機または fake backend で表示 | backend available | candidate と rejected reason が分かる |
| open/close E2E | 実機で claim/release | human approval, `PONKAN_RUN_N3DSXL=1` | 複数回成功 |

### 検証コマンド

```console
uv run pytest tests/unit/test_n3dsxl_device_filter.py tests/unit/test_n3dsxl_session.py
uv run ruff check src/py3dscapture tests/unit/test_n3dsxl_device_filter.py tests/unit/test_n3dsxl_session.py
uv run ty check --no-progress
```

実機 gate:

```console
$env:PONKAN_RUN_N3DSXL = "1"
$env:PONKAN_HARDWARE_APPROVED = "1"
uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_open_close.py
```

## 6. 実装チェックリスト

- [x] fake backend と device info 型を作る。
- [x] N3DSXL classifier を TDD で実装する。
- [x] `list_devices` CLI を追加する。
- [x] session open / close の fake backend test を追加する。
- [x] `N3DSXLDevice.open()` と `close()` を実装する。
- [x] 実機 E2E test に `requires_n3dsxl` marker を付ける。
- [x] local unit gate を実行する。
- [x] 実機 gate は人間承認まで未実行として報告する。
