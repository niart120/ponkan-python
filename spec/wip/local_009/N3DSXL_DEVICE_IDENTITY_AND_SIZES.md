# N3DSXL Device Identity And Sizes 仕様書

更新日: 2026-06-07

## 1. 概要

### 1.1 目的

Step 0 として、new 3DS XL capture board の USB identity、interface、endpoint、screen size、raw capture size を Python 側の定数と単体テストで固定する。

この Work Unit は後続の device listing、FTD3 command pipe、raw capture、streaming の安全境界になる。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| N3DSXL | MVP の Tier 0 device。USB product string は `N3DSXL` または `N3DSXL.2`。 |
| Accepted PID | `0x601e`, `0x601f`, `0x602a`, `0x602b`, `0x602c`, `0x602d`, `0x602f`。 |
| Command Interface | FTD3 command pipe に使う USB interface。N3DSXL では `0`。 |
| Bulk Interface | raw capture read/write に使う USB interface。N3DSXL では `1`。 |
| Video Size | raw payload 先頭の RGB8 video bytes。2D は `518400`、3D は `806400`。 |
| Capture Size | cc3dsfs の capture struct total を 1024 byte 境界へ切り下げた transfer size。 |
| Error Buffer | capture struct 末尾の error 領域。MVP ではここへ入る read を正常 video として扱わない。 |

### 1.3 背景・問題

未知の FTDI device に N3DSXL command を送ると安全上問題がある。後続 Step はすべて device identity と capture size に依存するため、最初に pure function と定数として固定し、実機なしで検証できる状態にする。

初期仕様では `include/hw_defs.hpp` と `include/capture_structs.hpp` が参照元として挙げられている。現行実装では `src/py3dscapture/protocol/sizes.py` に定数と size 計算があり、`tests/unit/test_n3dsxl_sizes.py` に単体テストがある。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| 誤 device 防止 | 後続実装ごとに判定する可能性 | identity 定数を single source にする |
| size 計算 | 初期仕様の文章に存在 | pure function と単体テストで固定する |
| 実機不要検証 | 一部実装済み | Step 0 の regression を unit test だけで確認する |
| source audit | 初期仕様由来 | 実装変更時に原典 path / URL を追記できる |

### 1.5 着手条件

- [x] `spec/initial/cc3dsfs_python_rebuild_spec.md` に N3DSXL identity と size がある。
- [x] `src/py3dscapture/protocol/sizes.py` が存在する。
- [x] `tests/unit/test_n3dsxl_sizes.py` が存在する。
- [x] この Work Unit の検証 command が通っている。

### 1.6 Work Unit メタデータ

| 項目 | 内容 |
| ---- | ---- |
| 配置 | `spec/wip/local_009/N3DSXL_DEVICE_IDENTITY_AND_SIZES.md` |
| 対応 Step | Step 0: constants and size tests |
| 前提 Work Unit | なし |
| 次 Work Unit | `spec/wip/local_010/N3DSXL_DEVICE_DISCOVERY_AND_SESSION.md` |
| 実装状態 | 現行実装あり。Step 0 の追加実装は原典再 audit や validation helper が必要になった場合だけ扱う。 |
| 選択条件 | identity / size の regression が壊れた、または後続 Step から transfer length validation helper が戻されたとき。 |
| 完了証拠 | `tests/unit/test_n3dsxl_sizes.py` と `tests/unit/test_package.py` が通り、後続仕様が magic number を再定義しない。 |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `src/py3dscapture/protocol/sizes.py` | 修正 | N3DSXL identity、screen size、capture size 計算を保持する。 |
| `src/py3dscapture/__init__.py` | 修正 | public API として必要な定数・関数を export する。 |
| `tests/unit/test_n3dsxl_sizes.py` | 修正 | identity と size 計算の regression test を保持する。 |
| `tests/unit/test_package.py` | 修正 | package import と export を確認する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| vendor ID を返す | N3DSXL identity を参照する | `0x0403` を返す | FTDI VID |
| accepted PID を返す | N3DSXL identity を参照する | 7個の PID set を返す | 順序を意味にしないため `frozenset` |
| accepted product string を返す | N3DSXL identity を参照する | `N3DSXL`, `N3DSXL.2` の set を返す | product string 不明は後続 Step で拒否 |
| USB interface / endpoint を返す | 後続 transport が定数を参照する | command interface `0`、bulk interface `1`、OUT `0x02`、IN `0x82` | N3DSXL 専用 |
| 2D video size を計算する | `mode_3d=False` | `240 * (400 + 320) * 3 = 518400` | RGB8 |
| 3D video size を計算する | `mode_3d=True` | `240 * (400 + 320 + 400) * 3 = 806400` | MVP の streaming 3D 切替は非対象 |
| capture size を計算する | mode を指定する | struct total を 1024 byte 境界へ切り下げる | 2D `555008`、3D `842752` |
| max non-error transferred を計算する | mode を指定する | `capture_size - 1024` を返す | error buffer 領域回避 |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | USB identity constants が初期仕様と一致する | regression | 3.1 | `test_n3dsxl_usb_identity_constants_match_spec` |
| green | USB interface constants が初期仕様と一致する | regression | 3.1 | `test_n3dsxl_usb_interface_constants_match_spec` |
| green | 2D capture sizes が初期仕様と一致する | regression | 3.1 | `test_n3dsxl_2d_capture_sizes_match_spec` |
| green | 3D capture sizes が初期仕様と一致する | regression | 3.1 | `test_n3dsxl_3d_capture_sizes_match_spec` |
| todo | `capture_sizes()` が `CaptureSizes.audio_size == 35072` を返す | regression | 3.1 | 現行実装で `audio_size` に `AUDIO_SIZE_BYTES` が入っているか確認する |
| todo | transferred length validation helper を追加する | new behavior | 3.1 | Step 5 の raw capture 実装前に検討する |

### 3.3 設計方針

この Work Unit は副作用を持たない。device enumeration や libusb access は実装しない。

定数は `protocol/sizes.py` に置き、後続 layer は magic number を直接持たない。型は Python 3.12+ の組み込み generics と `Final` を使う。

source audit 状態:

| 値 | 参照元 | 状態 |
| -- | ------ | ---- |
| VID/PID/product string/interface/endpoint | `spec/initial/cc3dsfs_python_rebuild_spec.md`、`include/hw_defs.hpp` | 初期仕様由来。原典再 audit は必要時に実施。 |
| video size | `spec/initial/cc3dsfs_python_rebuild_spec.md`、`include/capture_structs.hpp` | 初期仕様由来。 |
| capture size | `spec/initial/cc3dsfs_python_rebuild_spec.md`、`include/capture_structs.hpp` | 初期仕様由来。実機 raw dump で transferred を確認する。 |

### 3.4 Agentic SDD Task Graph

| 分類 | Task | Gate |
| ---- | ---- | ---- |
| Blocking local task | USB identity constants の regression を確認する | `tests/unit/test_n3dsxl_sizes.py` |
| Blocking local task | 2D / 3D capture size 計算の regression を確認する | `tests/unit/test_n3dsxl_sizes.py` |
| Sidecar task | constants を変更する場合だけ原典再 audit を行う | `cc3dsfs-source-audit` result |
| Hardware task | なし | not applicable |

この仕様を選んだ場合、Main Agent は新規実装よりも regression 維持を優先する。後続仕様から validation helper が戻された場合だけ、`errors.py` の例外階層が整った後に追加 TDD item として扱う。

## 4. 実装仕様

公開される最小 API:

```python
N3DSXL_VENDOR_ID: Final[int]
ACCEPTED_N3DSXL_PRODUCT_IDS: Final[frozenset[int]]
ACCEPTED_N3DSXL_PRODUCT_STRINGS: Final[frozenset[str]]

N3DSXL_COMMAND_INTERFACE: Final[int]
N3DSXL_BULK_INTERFACE: Final[int]
N3DSXL_BULK_OUT_ENDPOINT: Final[int]
N3DSXL_BULK_IN_ENDPOINT: Final[int]
N3DSXL_FTD3_COMMAND_PIPE_ID: Final[int]
N3DSXL_DEFAULT_CONFIGURATION: Final[int]

def video_size(mode_3d: bool) -> int: ...
def struct_total_before_1024_floor(mode_3d: bool) -> int: ...
def capture_size(mode_3d: bool) -> int: ...
def max_non_error_transferred(mode_3d: bool) -> int: ...
def capture_sizes(mode_3d: bool) -> CaptureSizes: ...
```

`CaptureSizes` は immutable dataclass にする。

```python
@dataclass(frozen=True, slots=True)
class CaptureSizes:
    mode_3d: bool
    video_size: int
    audio_size: int
    struct_total_before_1024_floor: int
    capture_size: int
    max_non_error_transferred: int
```

将来 Step 5 で raw transfer validation helper を追加する場合は、例外型が `errors.py` に存在してから実装する。

```python
def validate_transferred_length(transferred: int, sizes: CaptureSizes) -> None:
    if transferred < sizes.video_size:
        raise TransferTimeout(...)
    if transferred > sizes.max_non_error_transferred:
        raise TransferOverflow(...)
```

この helper は Step 0 の必須成果物ではなく、Step 5 の raw capture spec から戻る TDD item として扱える。

### 4.1 Agentic SDD 完了境界

この仕様は、USB device へアクセスしない pure logic の Work Unit として完了させる。Main Agent はこの仕様を選んだ場合、次を completion evidence として残す。

```text
- changed files: protocol/sizes.py, package export, unit tests
- tests: unit tests for identity and capture sizes
- source audit: initial spec based, re-audit only when constants change
- hardware: not applicable
- handoff: local_010 device discovery can import these constants
```

完了後に `local_010` へ進む場合、`N3DSXL_VENDOR_ID`、accepted PIDs、product strings、interface、endpoint、`capture_size(False)` を直接再定義しない。

### 4.2 完了判定

| 判定 | 必須 evidence |
| ---- | ------------- |
| local complete | identity constants、interface constants、2D / 3D capture size tests が通る |
| source-audit pending | 初期仕様由来の値を変更しない限り pending ではなく not required と扱う |
| hardware | not applicable。USB access は `local_010` 以降で扱う |
| handoff complete | `local_010` が `protocol/sizes.py` から constants を import する方針を守れる |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| identity constants | VID/PID/product string | なし | 初期仕様の値と一致 |
| interface constants | interface / endpoint | なし | 初期仕様の値と一致 |
| `capture_sizes(False)` | 2D size | `False` | `518400`, `555008`, `553984` |
| `capture_sizes(True)` | 3D size | `True` | `806400`, `842752`, `841728` |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| package import | public export が壊れていない | package installable | `import py3dscapture` が成功する |
| 後続 Step 参照 | device listing が定数を import する | Step 1 実装後 | magic number を重複定義しない |

### 検証コマンド

```console
uv run pytest tests/unit/test_n3dsxl_sizes.py tests/unit/test_package.py
uv run ruff check src/py3dscapture/protocol/sizes.py tests/unit/test_n3dsxl_sizes.py
uv run ty check --no-progress
```

## 6. 実装チェックリスト

- [x] N3DSXL USB identity constants を定義する。
- [x] interface / endpoint constants を定義する。
- [x] 2D / 3D video size を計算する。
- [x] capture size と max non-error transferred を計算する。
- [x] unit test を追加する。
- [x] 検証 command を実行する。
- [ ] 原典再 audit が必要になった場合、`cc3dsfs-source-audit` で path / URL を記録する。
