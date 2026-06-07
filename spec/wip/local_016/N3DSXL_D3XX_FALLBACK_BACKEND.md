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
| `tests/e2e/` | 修正 | D3XX backend の open-close / pipe / connect / raw capture gate を追加または parameterize する。 |

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

参照元:

- https://github.com/Lorenzooone/cc3dsfs/blob/main/CMakeLists.txt
- https://raw.githubusercontent.com/Lorenzooone/cc3dsfs/main/source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_compatibility.cpp
- https://raw.githubusercontent.com/Lorenzooone/cc3dsfs/main/source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_libusb_comms.cpp
- https://raw.githubusercontent.com/Lorenzooone/cc3dsfs/main/source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_shared.cpp
- https://pypi.org/project/PyD3XX/
- https://github.com/S-Hector/PyD3XX
- https://pypi.org/project/ftd3xx/
- https://ftdichip.com/wp-content/uploads/2020/08/AN_379-D3xx-Programmers-Guide.pdf

## 7. 実装チェックリスト

- [x] D3XX Python binding 候補を調査し、採用条件を固定する。
- [ ] `Ftd3Transport` Protocol と libusb adapter を導入する。
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
| unit targeted | pass | `uv run pytest tests/unit/test_d3xx_backend.py -q`: 4 passed |
| unit fallback selector | pass | `uv run pytest tests/unit/test_ftd3_backend_selector.py -q`: 2 passed |
| unit | pass | `uv run pytest tests/unit`: 70 passed |
| format | pass | `uv run ruff format --check .`: 57 files already formatted |
| lint | pass | `uv run ruff check .`: All checks passed |
| type | pass | `uv run ty check --no-progress`: All checks passed |
| lock | pass | `uv lock --check`: resolved lock is current |
| e2e skip | pass | `uv run pytest tests/e2e`: 5 skipped by `PONKAN_RUN_N3DSXL` gate |
| hardware D3XX read/write/raw | not run | `FT_ReadPipe` / `FT_WritePipe`、N3DSXL command、raw capture はまだ実行していない。 |
