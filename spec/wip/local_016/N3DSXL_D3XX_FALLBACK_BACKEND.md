# N3DSXL D3XX Fallback Backend 仕様書

## 1. 概要

### 1.1 目的

Windows で N3DSXL capture board が FTDI D3XX driver (`FTDIBUS3`) に bind され、libusb backend が `LIBUSB_ERROR_NOT_FOUND` で open できない場合に、FTDI D3XX API を使う fallback backend で open / pipe I/O / streaming gate へ進める。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| D3XX backend | FTDI D3XX API (`FT_CreateDeviceInfoList`, `FT_Open`, `FT_ReadPipe`, `FT_WritePipe` など) を使う N3DSXL 用 transport backend。 |
| libusb backend | 既存の `Usb1Backend`。WinUSB/libusbK/libusb compatible driver で device を開く。 |
| fallback | libusb listing/open が driver/backend mismatch を示す場合だけ D3XX backend を試す選択。 |
| FTDIBUS3 | 今回の実機で確認した Windows PnP service。FTDI FT600 USB 3.0 Bridge Device に bind されていた。 |
| backend identity | `backend_kind`、VID/PID、product string/status、serial、driver/service など、実機 artifact に残す識別情報。 |

### 1.3 背景・問題

`local_015` で product string unreadable は candidate 化できるようになったが、実機 open-close gate は `libusb_open` が `LIBUSB_ERROR_NOT_FOUND [-5]` を返して blocked になった。Windows PnP では device は `FTDI FT600 USB 3.0 Bridge Device`、service は `FTDIBUS3`、bus reported description は `N3DSXL.2` と確認済みである。

cc3dsfs は N3DSXL/FTD3 で libusb と FTDI D3XX driver backend の両方を build 対象にし、libusb 側が unsupported / not found を示す場合に driver backend 側も列挙する互換層を持つ。ponkan-python でも、driver を WinUSB/libusbK に差し替える前提だけにせず、現状 driver で進める fallback backend を検討する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| Windows + `FTDIBUS3` open | libusb open が `LIBUSB_ERROR_NOT_FOUND` | D3XX backend で open / close できる |
| driver 変更要求 | WinUSB/libusbK への切替が必要 | 既存 FTDI D3XX driver のまま検証できる |
| backend 記録 | libusb 前提の metadata | `backend_kind=d3xx` と driver/service を artifact に残す |
| cc3dsfs 追従性 | libusb path のみ | cc3dsfs の compatibility path と同じ設計判断を持つ |

### 1.5 着手条件

- [x] `local_015` により accepted VID/PID + unreadable product string を candidate として扱える。
- [x] 実機 listing で `0x0403:0x601e product_status=unreadable` が確認済み。
- [x] 実機 open-close が `LIBUSB_ERROR_NOT_FOUND [-5]` / `FTDIBUS3` で blocked であることを記録済み。
- [x] Python から利用する D3XX binding 候補を source audit し、最小 probe で import / DLL load 可否を確認する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `src/py3dscapture/transport/d3xx_backend.py` | 新規 | D3XX device enumeration、open/close、pipe read/write primitive を提供する。 |
| `src/py3dscapture/transport/ftd3_backend.py` | 新規 | libusb / D3XX の共通 FTD3 transport Protocol と adapter を定義する。 |
| `src/py3dscapture/devices/n3dsxl_ftd3.py` | 修正 | backend selection と D3XX candidate を扱える session layer にする。 |
| `src/py3dscapture/transport/ftd3_pipe.py` | 修正 | D3XX backend では D3XX native pipe API を使い、libusb command wrapper と分岐する。 |
| `src/py3dscapture/tools/list_devices.py` | 修正 | backend kind と fallback 状態を表示する。 |
| `src/py3dscapture/hardware_gate.py` | 修正 | `backend_kind` と Windows driver/service を command plan に記録する。 |
| `tests/unit/` | 修正/新規 | binding を fake 化した D3XX backend と fallback selection を unit test する。 |
| `tests/e2e/test_n3dsxl_d3xx_backend.py` | 新規 | D3XX backend の open-close / native pipe setup / fallback selector / connect gate を追加する。 |
| `tests/e2e/` | 修正 | raw capture gate を D3XX backend へ追加または parameterize する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| D3XX device を列挙する | D3XX binding が利用可能 | accepted VID/PID または accepted product evidence の device を candidate 化する | product unreadable は local_015 policy に従う |
| libusb 成功時 | libusb backend で open 可能 | libusb backend を使う | 既存 path を優先 |
| libusb driver mismatch | libusb open/listing が `LIBUSB_ERROR_NOT_FOUND` / `LIBUSB_ERROR_NOT_SUPPORTED` 相当 | D3XX backend を試す | cc3dsfs compatibility path に合わせる |
| D3XX open-close | `FTDIBUS3` bound device | D3XX handle を open し close できる | N3DSXL vendor command は送らない |
| D3XX pipe I/O | open 済み D3XX session | `FT_WritePipe` / `FT_ReadPipe` / `FT_SetStreamPipe` / `FT_AbortPipe` を使う | libusb FTD3 command wrapper は使わない |
| metadata を記録する | capture / stats / hardware plan | `backend_kind=d3xx`、VID/PID、product status、driver/service を含める | 後から backend 差を追える |
| binding 不在 | D3XX DLL / Python binding がない | 明示的に unavailable として skip / fallback failure を報告 | import error を握り潰さない |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | D3XX binding fake から device candidate を列挙できる | unit | 3.1 | no hardware |
| green | libusb unsupported/not-found のとき D3XX fallback が選ばれる | unit | 3.1 | fallback selection |
| green | libusb success のとき D3XX fallback を試さない | unit | 3.1 | regression |
| green | D3XX open-close が cleanup を保証する | unit | 3.1 | fake handle |
| green | D3XX pipe API が read/write/set/abort を native call へ写像する | unit | 3.1 | no command payload |
| green | metadata / command plan に backend identity が入る | unit | 3.1 | artifact traceability |
| green | 実機 D3XX open-close が成功する | hardware | 3.1 | `requires_n3dsxl` 相当の承認付き probe |
| green | 実機 D3XX create/abort or native pipe setup が成功する | hardware | 3.1 | `FT_AbortPipe(0x82)` / `FT_SetStreamPipe(0x82, 1024)` |
| deferred | 実機 D3XX raw capture が `.bin` / `.json` を保存する | hardware | 3.1 | local_014 continuation |

### 3.3 設計方針

D3XX backend は libusb backend の内部実装に混ぜない。`N3DSXLDevice` が握る session handle は「configuration/claim がある libusb handle」と「FTDI native handle」で lifecycle が違うため、FTD3 transport Protocol を新設し、protocol layer からは pipe operation の違いを隠す。

fallback は「libusb を試したあと常に D3XX」ではなく、driver/backend mismatch と判断できる場合だけ発火する。D3XX binding がない環境では import 時に失敗させず、backend unavailable として listing / tests に報告する。

## 4. 実装仕様

```python
BackendKind = Literal["libusb", "d3xx"]

@dataclass(frozen=True, slots=True)
class BackendIdentity:
    backend_kind: BackendKind
    driver_service: str | None
    product_string_status: Literal["accepted", "unreadable"]

class Ftd3Transport(Protocol):
    backend_kind: BackendKind

    def close(self) -> None: ...
    def abort_pipe(self, pipe: int) -> None: ...
    def set_stream_pipe(self, pipe: int, length: int) -> None: ...
    def read_pipe(self, pipe: int, length: int, timeout_ms: int) -> bytes: ...
    def write_pipe(self, pipe: int, payload: bytes, timeout_ms: int) -> int: ...
```

D3XX backend は、最初の実装では Windows + FT600/N3DSXL だけを対象にする。Linux/macOS では libusb path を優先し、D3XX fallback は unavailable として扱う。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| D3XX adapter | binding fake の enumeration | fake `FT_CreateDeviceInfoList` | candidate |
| fallback selector | libusb not-found | fake libusb error | D3XX backend 選択 |
| fallback selector | libusb success | fake libusb handle | D3XX 未使用 |
| pipe adapter | native pipe call mapping | fake `FT_ReadPipe` | bytes / transferred |
| cleanup | open failure / close failure | fake exception | close attempted |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| D3XX listing | 実機を candidate として表示 | D3XX binding available, human approval | `backend=d3xx` |
| D3XX open-close | handle lifecycle | `PONKAN_RUN_N3DSXL=1`, approval | open / close success |
| D3XX raw capture | frame acquisition | open-close pass 後 | `.bin` と `.json` 保存 |

### 検証コマンド

```console
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

実機検証:

```console
$env:PONKAN_RUN_N3DSXL = "1"
$env:PONKAN_HARDWARE_APPROVED = "1"
uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_open_close.py
```

## 6. Source Audit

| 項目 | 状態 | 根拠 |
| ---- | ---- | ---- |
| cc3dsfs は N3DSXL FTD3 で libusb と D3XX driver backend を両方 build する | fact | `CMakeLists.txt` の `USE_FTD3XX_FOR_N3DSXL_LOOPY` / `USE_LIBUSB_FOR_N3DSXL_LOOPY` と source list。 |
| Windows 以外では FTD3XX backend を無効化する | fact | `CMakeLists.txt` の `NOT Windows` branch。 |
| compatibility layer は libusb 後に D3XX driver listing を試す | fact | `3dscapture_ftd3_compatibility.cpp` の `ftd3_list_devices_compat`。 |
| libusb `LIBUSB_ERROR_NOT_FOUND` は FTD3XX driver bound 時の failure として扱われる | fact | `3dscapture_ftd3_libusb_comms.cpp` の `ftd3_libusb_list_devices` comment。 |
| D3XX backend の Python binding は未確定だった | resolved hypothesis | `ftd3xx` / `PyD3XX` を比較し、初期採用を `PyD3XX` に固定した。 |
| Python binding は `PyD3XX` を optional dependency として採用する | fact | PyPI `PyD3XX 1.1.4` は Python `>=3.10`、FT60x/D3XX wrapper、Windows/Linux/macOS support、D3XX dynamic library 同梱を掲げる。 |
| 旧 `ftd3xx` package は初期採用しない | fact | PyPI `ftd3xx 1.0` は 2023-04-06 release、system D3XX driver / `ftd3xx.dll` 前提で、更新頻度と同梱性が `PyD3XX` より弱い。 |
| ローカル probe で `PyD3XX` import と D3XX library load は成功した | fact | `uv run python -c "import PyD3XX; ... FT_GetLibraryVersion()"` が `(0, 16973840)` を返した。device enumeration / open は未実行。 |
| PyD3XX の `FT_Create` は初期化済み device detail を渡す必要がある | fact | 新規 `FT_Device()` では `FT_OTHER_ERROR`。`FT_GetDeviceInfoDetail(0)` が返した object では index / serial / description open-close が成功した。 |
| PyD3XX wrapper の `FT_WritePipe` は今回の実機で `FT_OTHER_ERROR` を返す | fact | `D3xxHandle.write_pipe()` が PyD3XX wrapper 経由のとき、connect sequence の最初の 4 byte write で status `32`。同梱 D3XX DLL への ctypes direct `FT_WritePipe` では status `0` / transferred `4`。 |
| cc3dsfs の D3XX connect は drain 後に一度 close / reconnect する | fact | `3dscapture_ftd3_shared.cpp` の `connect_ftd3`: `drain_data` 後に `preemptive_close_connection` を呼び、同じ serial で `ftd3_reconnect_compat` を再実行してから SPI / firmware / config read に進む。 |
| ponkan-python の現 D3XX connect は drain 後 reconnect をしていない | fact | `N3DSXLProtocol.connect()` は `create_pipe` / `drain` / `abort` / `create_pipe` の後、同じ `D3xxHandle` で SPI / firmware / config read に進む。D3XX backend の `create_pipe()` は no-op。 |
| D3XX read/write timeout handling は原典に近づけた | fact | `3dscapture_ftd3_compatibility.cpp` は `FT_GetPipeTimeout` / `FT_SetPipeTimeout` で timeout を一時設定し、read/write 後に復元する。現実装も direct DLL path で同じ保存・設定・復元を行う。 |
| firmware load 後 200ms wait は原典に近づけた | fact | `3dscapture_ftd3_shared.cpp` の `load_3ds_cc_firmware` は firmware write 後に `FTD3_N3DSXL_CFG_WAIT_MS` を待つ。現実装も `N3DSXL_CFG_WAIT_MS` を待つ。 |
| Windows D3XX raw capture は command read と別 API を使う | fact | `3dscapture_ftd3_driver_acquisition.cpp` は Windows の capture read で `FT_ReadPipeEx` を使う。現時点の failure は connect 中の config read であり、raw capture API 差分は未検証。 |

### 6.1 D3XX connect failure analysis

2026-06-08 の実機 gate では、対象 device は `0x0403:0x601e product=N3DSXL.2 serial=nxl530228 flags=4` として D3XX listing に復帰した。`tests/e2e/test_n3dsxl_d3xx_backend.py -q` は open-close、native pipe setup、fallback selector が pass し、connect だけが `_read_3ds_config_3d()` の `FT_ReadPipe(0x82, 0x10)` status `32` で失敗した。直後の listing は `flags=4` のままで、handle cleanup は成功している。

確定している切り分け:

| 観点 | 状態 | 判断 |
| ---- | ---- | ---- |
| device identity | `0x0403:0x601e`, `N3DSXL.2`, `serial=nxl530228` | 対象 device は安全条件を満たす。 |
| D3XX visibility | listing / candidate 化は pass | product string / D3XX enumeration 問題ではない。 |
| handle lifecycle | open-close gate と e2e 後 listing は pass | 単純な close 漏れではない。 |
| native pipe setup | `FT_AbortPipe(0x82)` / `FT_SetStreamPipe(0x82, 1024)` は pass | pipe setup API 自体は呼べている。 |
| write path | direct DLL `FT_WritePipe` で最初の write は前進 | PyD3XX wrapper の write failure は direct path で回避済み。 |
| read path | config read の `FT_ReadPipe(0x82, 0x10)` が status `32` | 残 blocker は config read 直前の device / pipe state 差分。 |

原典との差分と仮説:

| ID | 仮説 | 根拠 | 次に確認すること |
| -- | ---- | ---- | ---------------- |
| H1 | drain 後 reconnect 不足が config read failure の主因 | cc3dsfs は `drain_data` 後に `preemptive_close_connection` してから reconnect する。Python D3XX path は同一 handle のまま進んでいた。 | verified: D3XX connect sequence に drain 後 close / serial reconnect を導入したところ、D3XX e2e 4 件が pass。 |
| H2 | D3XX command read の pipe state が drain read の影響を受けている | failure は drain 後、SPI / firmware 後の config read に集中した。reconnect で state をリセットしていない点が H1 と連動する。 | verified through H1: reconnect 後は status `32` が再現しない。 |
| H3 | endpoint id と FIFO index の扱い差が config read に影響している | command read は原典も `FT_ReadPipe(handle, BULK_IN=0x82, ...)`。raw capture は Windows で `FT_ReadPipeEx` を使うが、今回の failure は raw capture 前。 | config read では H1 より優先しない。raw capture Work Unit で別途扱う。 |
| H4 | PyD3XX bundled DLL / driver version 相性がある | `FT_WritePipe` wrapper は status `32`、direct DLL path では write が前進した。 | H1 実装後も failure が残る場合に library / driver version と system DLL path を比較する。 |

H1 は検証済み。追加の探索的実機 probe は増やさず、次は raw capture / streaming gate へ進む。

参照元:

- https://github.com/Lorenzooone/cc3dsfs/blob/main/CMakeLists.txt
- https://raw.githubusercontent.com/Lorenzooone/cc3dsfs/main/source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_compatibility.cpp
- https://raw.githubusercontent.com/Lorenzooone/cc3dsfs/main/source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_libusb_comms.cpp
- https://raw.githubusercontent.com/Lorenzooone/cc3dsfs/main/source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_shared.cpp
- https://raw.githubusercontent.com/Lorenzooone/cc3dsfs/main/source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_driver_acquisition.cpp
- https://pypi.org/project/PyD3XX/
- https://github.com/S-Hector/PyD3XX
- https://pypi.org/project/ftd3xx/
- https://ftdichip.com/wp-content/uploads/2020/08/AN_379-D3xx-Programmers-Guide.pdf

## 7. 実装チェックリスト

- [x] D3XX Python binding 候補を調査し、採用条件を固定する。
- [x] `Ftd3Transport` Protocol と libusb adapter を導入する。
- [x] D3XX enumeration / open-close adapter を fake binding で TDD 実装する。
- [x] D3XX pipe adapter を fake binding で TDD 実装する。
- [x] fallback selector を追加する。
- [x] metadata / hardware gate に backend identity を追加する。
- [x] 実機 D3XX listing / open-close gate を承認後に実行する。
- [ ] raw capture / streaming gate を D3XX backend で再開する。

## 8. Gate 結果

| Gate | 結果 | 証拠 |
| ---- | ---- | ---- |
| D3XX import probe | pass | `uv run python -c "import PyD3XX; ... FT_GetLibraryVersion()"`: `(0, 16973840)` |
| D3XX listing probe | pass | `d3xx_device_count 1`; `0x0403:0x601e product=N3DSXL.2 serial=nxl530228 flags=4` |
| D3XX open-close probe | pass | `D3xxBackend.open status ok`; `D3xxHandle.close status ok` |
| D3XX native pipe setup probe | pass | `D3xxHandle.abort_pipe 0x82 status ok`; `D3xxHandle.set_stream_pipe 0x82 length=1024 status ok` |
| D3XX fallback selector probe | pass | libusb candidate `0x0403:0x601e product=- product_status=unreadable`; `selected_backend d3xx`; `transport_close status ok` |
| D3XX connect probe | blocked | direct DLL `FT_WritePipe` により write は前進したが、`_read_3ds_config_3d()` の `FT_ReadPipe(0x82, 0x10)` が status `32`。再接続後、cc3dsfs と同じ firmware load 後 200ms wait を追加して再試行したところ、同期 read が 60s timeout まで戻らず stale-open になった。 |
| D3XX e2e gate file | partial | 再接続後の `uv run pytest tests/e2e/test_n3dsxl_d3xx_backend.py -q`: open-close / native pipe setup / fallback selector は pass、connect は `FT_ReadPipe` status `32`。200ms wait 修正後の再実行は command timeout。 |
| D3XX listing recovery | blocked | `D3xxBackend().iter_devices()` は 1 件だが `id=0x00000000 flags=1 product=- serial=-`。`flags=1` は `FT_FLAGS_OPENED`。repo 由来 python/uv process は残っていない。PnP は `FTDI FT600 USB 3.0 Bridge Device` / `USB Composite Device` とも `OK`。`pnputil /restart-device` は `Access is denied`。libusb listing では candidate `0x0403:0x601e product=- product_status=unreadable` が見えている。 |
| D3XX listing after physical replug | pass | `d3xx_device_count 1`; `device index=0 id=0x0403601e vid=0x0403 pid=0x601e product=N3DSXL.2 serial=nxl530228 flags=4`; `d3xx_candidate_count 1`。 |
| D3XX e2e after timeout handling | partial | 2026-06-08: `uv run pytest tests/e2e/test_n3dsxl_d3xx_backend.py -q` は 3 passed / 1 failed。connect は `_read_3ds_config_3d()` の `FT_ReadPipe(0x82, 0x10)` status `32`。直後の listing は `flags=4` / candidate 1 件で stale-open なし。 |
| D3XX e2e after drain reconnect | pass | 2026-06-08: `uv run pytest tests/e2e/test_n3dsxl_d3xx_backend.py -q`: 4 passed。直後の listing は `flags=4` / candidate 1 件で stale-open なし。 |
| unit targeted | pass | `uv run pytest tests/unit/test_n3dsxl_connect_sequence.py tests/unit/test_d3xx_backend.py -q`: 12 passed |
| unit connect sequence targeted | pass | `uv run pytest tests/unit/test_n3dsxl_connect_sequence.py -q`: 7 passed |
| lint targeted | pass | `uv run ruff check src\py3dscapture\protocol\n3dsxl.py src\py3dscapture\transport\d3xx_backend.py src\py3dscapture\transport\ftd3_pipe.py tests\unit\test_n3dsxl_connect_sequence.py tests\unit\test_d3xx_backend.py`: All checks passed |
| unit fallback selector | pass | `uv run pytest tests/unit/test_ftd3_backend_selector.py -q`: 2 passed |
| unit | pass | `uv run pytest tests/unit -q`: 74 passed |
| format | pass | `uv run ruff format --check .`: 58 files already formatted |
| lint | pass | `uv run ruff check .`: All checks passed |
| type | pass | `uv run ty check --no-progress`: All checks passed |
| lock | pass | `uv lock --check`: resolved lock is current |
| e2e skip | pass | `uv run pytest tests/e2e`: 5 skipped by `PONKAN_RUN_N3DSXL` gate |
| hardware D3XX read/write/raw | not run | `FT_ReadPipe` / `FT_WritePipe`、N3DSXL command、raw capture はまだ実行していない。 |
