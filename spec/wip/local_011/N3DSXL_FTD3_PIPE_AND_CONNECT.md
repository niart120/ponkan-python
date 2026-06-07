# N3DSXL FTD3 Pipe And Connect 仕様書

更新日: 2026-06-07

## 1. 概要

### 1.1 目的

Step 3-4 として、N3DSXL session 上で FTD3 command pipe を扱い、2D default stream setup までの connect sequence を実装する。

この Work Unit は USB command を扱うため、実装前に `cc3dsfs` 原典の command payload と sequence を source audit で固定する。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| FTD3 Command Pipe | N3DSXL の create / abort / set stream / prepare read / prepare write を送る command wrapper。 |
| Pipe ID | command pipe `0x01`、create pipe id `0x82`、bulk pipe id `0x01`。 |
| Prepare Command | bulk read/write 前に command pipe へ送る read/write prepare。 |
| Connect Sequence | open/claim 済み device に対して drain、reset 相当、SPI/config、stream setup を行う sequence。 |
| Dry-run Logging | 実機送信前に command name、payload length、pipe、target length を記録する mode。 |

### 1.3 背景・問題

new 3DS XL は単純な bulk IN device ではなく、FTD3 command wrapper を通して pipe setup と read/write prepare を行う。command 値を誤ると未知の device 操作になるため、payload builder は単体テストで固定し、実機送信は identity guard と人間承認の後に行う。

`spec/initial` では Step 3 が FTD3 command pipe、Step 4 が connect sequence である。この仕様では、payload builder、command sender、connect orchestration を分ける。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| command payload | 実装なし | 原典 audit 済み payload builder と characterization test を持つ |
| identity guard | Step 1-2 に依存 | Candidate 以外では command を送らない |
| connect failure | 実装なし | 失敗 command、libusb status、payload length をログに残す |
| 2D setup | 実装なし | `mode_3d=False` の stream pipe setup まで完了する |

### 1.5 着手条件

- [x] `spec/complete/local_010/N3DSXL_DEVICE_DISCOVERY_AND_SESSION.md` の safe open / claim が実装済み。
- [ ] `cc3dsfs-source-audit` で command payload、timeout、connect sequence の参照元を記録済み。
- [ ] 実機 E2E を実行する場合、人間承認がある。

### 1.6 Work Unit メタデータ

| 項目 | 内容 |
| ---- | ---- |
| 配置 | `spec/wip/local_011/N3DSXL_FTD3_PIPE_AND_CONNECT.md` |
| 対応 Step | Step 3: FTD3 command pipe、Step 4: connect sequence |
| 前提 Work Unit | `spec/complete/local_010/N3DSXL_DEVICE_DISCOVERY_AND_SESSION.md` |
| 次 Work Unit | `spec/wip/local_012/N3DSXL_RAW_CAPTURE_FIXTURE_AND_DECODER.md` |
| local task | payload builder、fake backend read/write order、connect sequence characterization。 |
| sidecar task | `cc3dsfs-source-audit` による command payload と sequence の原典確認。 |
| hardware task | create/abort/set_stream/connect の実機 E2E。 |
| 選択条件 | safe session が実装済みで、raw frame read 前の FTD3 pipe / connect が未実装のとき。 |
| 完了証拠 | payload characterization が原典 evidence と一致し、実機 command は承認待ちまたは実行結果つきで報告されている。 |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `src/py3dscapture/transport/ftd3_pipe.py` | 新規 | FTD3 command payload builder と pipe read/write wrapper を実装する。 |
| `src/py3dscapture/protocol/n3dsxl.py` | 新規 | N3DSXL connect sequence と 2D stream setup を実装する。 |
| `src/py3dscapture/errors.py` | 修正 | `Ftd3CommandError`, `UnsupportedDevice`, `DeviceDisconnected` などを追加する。 |
| `tests/unit/test_ftd3_pipe_payloads.py` | 新規 | command payload builder を characterization する。 |
| `tests/unit/test_n3dsxl_connect_sequence.py` | 新規 | fake pipe で sequence と guard を検証する。 |
| `tests/e2e/test_n3dsxl_ftd3_pipe.py` | 新規 | 実機 create/abort などを検証する。 |
| `tests/e2e/test_n3dsxl_connect.py` | 新規 | 実機 2D connect を検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| payload を構築する | command name、pipe、length | 原典と一致する bytes を返す | unit test で固定 |
| command を送る前に guard する | session が Candidate 由来ではない | `UnsupportedDevice` を送出し、USB command を送らない | safety |
| create pipe する | open/claim 済み session | command pipe create が成功する | 実機 gate |
| abort pipe する | pipe id を指定 | abort command が成功する | 実機 gate |
| set stream pipe する | pipe id、2D capture size | stream pipe が 2D size で設定される | Step 4 |
| read pipe する | pipe id、length、timeout | prepare read -> bulk IN の順に実行する | 単純 bulk read ではない |
| write pipe する | pipe id、payload、timeout | prepare write -> bulk OUT の順に実行する | 単純 bulk write ではない |
| connect する | N3DSXL session、`mode_3d=False` | drain/reset/SPI/config/stream setup を順に実行する | 詳細 sequence は source audit で固定 |
| connect 失敗を記録する | command が失敗する | command name、status、payload length、transferred を error に含める | debug 用 |
| 3D mode 切替を拒否する | streaming 中の mode change | `UnsupportedOperation` | MVP 外 |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | create pipe payload が source audit fixture と一致する | characterization | 3.1 | 原典 audit 後に fixture 化 |
| todo | abort pipe payload が source audit fixture と一致する | characterization | 3.1 | pipe id parameter |
| todo | set stream pipe payload に 2D capture size が入る | characterization | 3.1 | `capture_size(False)` |
| todo | read_pipe は prepare read 後に bulk IN を呼ぶ | new behavior | 3.1 | fake backend |
| todo | write_pipe は prepare write 後に bulk OUT を呼ぶ | new behavior | 3.1 | fake backend |
| todo | Candidate 由来でない session は command 送信前に拒否される | safety | 3.1 | fake session |
| todo | connect sequence が source audit の順序で pipe methods を呼ぶ | characterization | 3.1 | fake pipe |
| todo | connect 失敗時に command name と libusb status が error に残る | regression | 3.1 | debug |
| todo | 実機 create/abort が libusb error なしで返る | hardware | 3.1 | `requires_n3dsxl` |
| todo | 実機 2D connect が完了する | hardware | 3.1 | `requires_n3dsxl` |

### 3.3 設計方針

FTD3 command pipe は transport layer だが、N3DSXL の identity guard なしでは使わない。payload builder は pure function にし、sender は backend I/O を受け持つ。

Source Audit Gate:

| 項目 | 参照元候補 | 実装前状態 |
| ---- | ---------- | ---------- |
| create / destroy pipe command | `source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_libusb_comms.cpp` | audit required |
| abort pipe command | 同上 | audit required |
| read/write prepare command | 同上 | audit required |
| set stream pipe command | 同上 | audit required |
| connect sequence | `3dscapture_ftd3_shared.cpp`, `3dscapture_ftd3_compatibility.cpp` | audit required |
| timeouts | `3dscapture_ftd3_libusb_comms.cpp` | audit required |

Hardware Gate:

```text
- product string が N3DSXL / N3DSXL.2 であることを直前に確認する。
- command scope は create/abort/set_stream/connect のどれかを明示する。
- 実行前に PONKAN_HARDWARE_APPROVED=1 を同じ command 内で明示する。
- 失敗時も close が interface release / handle close を行う。
```

### 3.4 Agentic SDD Task Graph

| 分類 | Task | Gate |
| ---- | ---- | ---- |
| Blocking local task | command payload の source audit item を作る | `cc3dsfs-source-audit` result |
| Blocking local task | payload builder を characterization test で固定する | `tests/unit/test_ftd3_pipe_payloads.py` |
| Blocking local task | fake backend で prepare -> bulk の順序を固定する | read/write unit test |
| Blocking local task | fake pipe で connect sequence と failure context を固定する | `tests/unit/test_n3dsxl_connect_sequence.py` |
| Hardware task | create/abort/connect E2E を実行する | human approval、`requires_n3dsxl` |

この仕様は raw frame read を実装しない。`set_stream_pipe(capture_size(False))` までを handoff boundary とし、実際の frame payload 取得は `local_012` で扱う。

## 4. 実装仕様

### 4.1 Ftd3Pipe

```python
class Ftd3Pipe:
    def __init__(self, session: N3DSXLDevice, backend: LibusbBackend) -> None: ...

    def create_pipe(self) -> None: ...
    def abort_pipe(self, pipe: int) -> None: ...
    def set_stream_pipe(self, pipe: int, length: int) -> None: ...
    def read_pipe(self, pipe: int, length: int, timeout_ms: int = 500) -> bytes: ...
    def write_pipe(self, pipe: int, payload: bytes, timeout_ms: int = 500) -> int: ...
```

payload builders:

```python
def build_create_pipe_payload() -> bytes: ...
def build_abort_pipe_payload(pipe: int) -> bytes: ...
def build_set_stream_pipe_payload(pipe: int, length: int) -> bytes: ...
def build_prepare_read_payload(pipe: int, length: int) -> bytes: ...
def build_prepare_write_payload(pipe: int, length: int) -> bytes: ...
```

payload builder は endian、padding、command id を source audit fixture で固定する。source audit が終わるまで仮 payload で実機 command を送らない。

### 4.2 Connect

```python
class N3DSXLProtocol:
    def __init__(self, device: N3DSXLDevice, pipe: Ftd3Pipe) -> None: ...

    def connect(self, *, mode_3d: bool = False) -> None:
        if mode_3d:
            raise UnsupportedOperation("3D streaming is outside MVP bring-up")
        ...
```

2D connect の最低 sequence:

```text
1. identity guard
2. drain_data
3. preemptive reset / reopen 相当 sequence
4. SPI access / config read
5. firmware / mode command
6. 3D config read
7. set_stream_pipe(pipe=bulk pipe id, length=capture_size(False))
```

正確な command 数、payload、optional step は source audit と初回実機結果で更新する。

### 4.4 完了判定

| 判定 | 必須 evidence |
| ---- | ------------- |
| source-audit complete | command id、payload layout、timeout、connect sequence の原典 path / URL と検証状態が記録済み |
| local complete | payload characterization、fake backend order、connect sequence unit test が通る |
| hardware pending | 実機 command scope、device identity、cleanup、artifact 方針を示して承認待ち |
| hardware complete | `tests/e2e/test_n3dsxl_ftd3_pipe.py` と `tests/e2e/test_n3dsxl_connect.py` の結果を報告 |

### 4.3 Error

```python
@dataclass(frozen=True, slots=True)
class Ftd3CommandContext:
    command_name: str
    pipe: int | None
    payload_length: int
    requested_length: int | None
    transferred: int | None
    libusb_status: int | None

class Ftd3CommandError(CaptureError):
    context: Ftd3CommandContext
```

error message は短くし、詳細は context に入れる。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| payload builders | source audit fixture と一致 | command name | bytes 一致 |
| read_pipe | prepare -> bulk IN 順序 | fake backend | call log 一致 |
| write_pipe | prepare -> bulk OUT 順序 | fake backend | call log 一致 |
| guard | unsupported session | fake session | USB command call なし |
| connect sequence | 2D setup | fake pipe | audited order |
| error context | failed command | fake backend raises | command context が残る |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| FTD3 pipe E2E | create/abort が返る | human approval | libusb error なし |
| connect E2E | 2D default connect | human approval | set_stream_pipe まで成功 |

### 検証コマンド

```console
uv run pytest tests/unit/test_ftd3_pipe_payloads.py tests/unit/test_n3dsxl_connect_sequence.py
uv run ruff check src/py3dscapture tests/unit/test_ftd3_pipe_payloads.py tests/unit/test_n3dsxl_connect_sequence.py
uv run ty check --no-progress
```

実機 gate:

```console
$env:PONKAN_RUN_N3DSXL = "1"
$env:PONKAN_HARDWARE_APPROVED = "1"
uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_ftd3_pipe.py tests/e2e/test_n3dsxl_connect.py
```

## 6. 実装チェックリスト

- [ ] `cc3dsfs-source-audit` で FTD3 command payload と connect sequence を記録する。
- [ ] payload builder の characterization test を書く。
- [ ] `Ftd3Pipe` の fake backend unit test を書く。
- [ ] `Ftd3Pipe` を実装する。
- [ ] `N3DSXLProtocol.connect(mode_3d=False)` の fake sequence test を書く。
- [ ] connect sequence を実装する。
- [ ] 実機 E2E test に `requires_n3dsxl` marker を付ける。
- [ ] local unit gate を実行する。
- [ ] 実機 gate は人間承認まで未実行として報告する。
