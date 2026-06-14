# Structured Capture Errors 仕様書

更新日: 2026-06-15

## 1. 概要

### 1.1 目的

`CaptureError` hierarchy に `code`、`profile`、`backend`、`reason`、`recoverable`、`remediation` を持たせ、GUI や adapter が例外メッセージ文字列を解析せずに user log / status bar / technical log を分けられるようにする。`reason` は `local_029` の discovery reason と共通 enum にする。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| error code | 例外種別を機械的に識別する stable string。例: `device_not_found`。 |
| reason | 同じ error code 内で原因を絞る string。例: `missing_driver`。 |
| capture reason | discovery と error で共有する stable reason enum。`available` は discovery success 専用で、error では使わない。 |
| recoverable | retry、設定変更、device 接続で復旧し得るかを示す bool。 |
| remediation | UI や CLI が表示できる短い復旧案内。 |
| structured context | backend や profile など、呼び出し側が分岐に使う属性。 |

### 1.3 背景・問題

現行 exception hierarchy は `CaptureError` を基底に、`DeviceNotFound`、`DeviceOpenError`、`Ftd3CommandError`、`UnsupportedOperation`、`DecodeError`、`DependencyUnavailableError` などを持つ。`Ftd3CommandError` は `context` を持つが、他の例外は GUI が機械的に分岐しやすい common fields を持たない。

NyX のような GUI は user log、status bar、technical log を分ける必要がある。例外メッセージ文字列解析では locale / wording change に弱いため、ponkan-python 側で structured fields を提供する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| GUI 分岐 | 例外型と文字列に依存 | `code` / `reason` で分岐できる |
| backend context | 一部例外に限られる | common field で取得できる |
| remediation | message に埋め込み | `remediation` field として取得できる |
| recoverable 判断 | 呼び出し側が推測 | `recoverable` bool を参照できる |
| existing API | exception class は存在 | class 互換を維持しつつ fields を追加 |

### 1.5 着手条件

- [x] 現行 `src/ponkan/errors.py` の exception hierarchy を確認する。
- [x] `local_029` の device discovery reason と命名を合わせる。
- [x] 既存 unit test が例外メッセージに依存していないか確認する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/complete/local_030/STRUCTURED_CAPTURE_ERRORS.md` | 完了済み | structured error model の仕様を定義する。 |
| `src/ponkan/errors.py` | 修正 | `CaptureReason`、`CaptureError` common fields、subclass default を追加する。 |
| `src/ponkan/capture.py` | 修正 | profile / backend context を例外生成時に渡す。 |
| `src/ponkan/devices/discovery.py` | 後続 | `local_029` で新規作成時に `CaptureReason` を import して discovery reason と error reason を共有する。 |
| `src/ponkan/devices/n3dsxl_ftd3.py` | 修正 | rejected / unreadable / open failure context を structured にする。 |
| `docs/api.md` | 修正 | structured errors の扱いを追記する。 |
| `tests/unit/test_structured_capture_errors.py` | 新規 | fields、string compatibility、subclass defaults を検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| base error | `CaptureError(...)` | common fields を持つ | message は従来通り str で見える |
| device not found | device 候補なし | `code="device_not_found"`, `recoverable=True` | source は表示し未接続 status にできる |
| unsupported profile | unknown profile | `code="unsupported_profile"`, `reason="unsupported_profile"` | 通常 UI 非表示 |
| missing package | PyD3XX missing | `code="dependency_unavailable"`, `reason="missing_package"` | remediation 付き |
| device rejected | VID/PID/product string 不一致 | `code="device_rejected"` | safety warning |
| read failed | streaming read error | `code="read_failed"` | reconnect candidate |
| decode failed | raw decode error | `code="decode_failed"` | technical log |
| FTD3 context | command failure | 既存 `context` を維持し common fields も持つ | backward compatible |
| discovery との reason 共有 | backend / profile availability | `CaptureReason` を使う | `available` は discovery result 専用 |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | `CaptureError` は common fields を持つ | new behavior | 3.1 | default values |
| green | subclass は stable default `code` を持つ | contract | 3.1 | `DeviceNotFound` など |
| green | `str(error)` は既存 message と互換 | regression | 3.1 | user-visible text |
| green | `DependencyUnavailableError.for_backend_dependency` は `reason="missing_package"` と backend context を持つ | diagnostics | 3.1 | backend field |
| green | `Ftd3CommandError.context` は維持される | regression | 3.1 | existing tests |
| green | discovery と error が同じ `CaptureReason` を参照する | contract | 3.1 | local_029 連携 |
| green | error fields は JSON log に変換しやすい | integration | 3.1 | `to_dict()` optional |

### 3.3 設計方針

既存 exception class 名は維持する。利用側が `except DeviceNotFound` のように分岐している可能性があるため、class hierarchy の破壊はしない。

common fields は constructor kwargs で渡せるようにし、subclass は default `code` / `recoverable` を持つ。`Ftd3CommandError` の `context` は削除せず、common fields の `details` または `technical_context` として参照できるようにする。

`code` は exception category、`reason` は availability / failure cause として分ける。例えば `DependencyUnavailableError` の `code` は `dependency_unavailable`、`reason` は `missing_package` / `missing_driver` / `missing_runtime` のいずれかにできる。discovery success の `available` は同じ enum に含めるが、`CaptureError.reason` では使わない。

## 4. 実装仕様

```python
from typing import Literal

CaptureReason = Literal[
    "available",
    "missing_package",
    "missing_driver",
    "missing_runtime",
    "unsupported_platform",
    "unsupported_backend",
    "unsupported_profile",
    "device_not_found",
    "device_rejected",
    "open_failed",
    "read_failed",
    "decode_failed",
    "unknown",
]


class CaptureError(Exception):
    code: str
    profile: str | None
    backend: str | None
    reason: CaptureReason | None
    recoverable: bool
    remediation: str | None

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        profile: str | None = None,
        backend: str | None = None,
        reason: CaptureReason | None = None,
        recoverable: bool | None = None,
        remediation: str | None = None,
    ) -> None:
        ...
```

reason 候補:

| reason | 利用側の扱い |
| ------ | ------------ |
| `missing_package` | backend package guidance |
| `missing_driver` | driver guidance |
| `missing_runtime` | backend runtime guidance |
| `unsupported_platform` | disabled source |
| `unsupported_backend` | backend selector guidance |
| `unsupported_profile` | UI に出さない |
| `device_not_found` | 未接続 status |
| `device_rejected` | safety warning |
| `open_failed` | preview error |
| `read_failed` | runtime error / reconnect candidate |
| `decode_failed` | technical log |

subclass default:

| class | default code | recoverable |
| ----- | ------------ | ----------- |
| `DeviceNotFound` | `device_not_found` | `True` |
| `UnsupportedDevice` | `device_rejected` | `False` |
| `DeviceOpenError` | `open_failed` | `True` |
| `UnsupportedOperation` | `unsupported_operation` | `False` |
| `DecodeError` | `decode_failed` | `False` |
| `DependencyUnavailableError` | `dependency_unavailable` | `True` |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| base error | fields | kwargs | 属性が取得できる |
| subclass | default code | `DeviceNotFound()` | `code == "device_not_found"` |
| string | message compatibility | custom message | `str(error)` が message |
| dependency error | backend context | `for_backend_dependency("PyD3XX", "d3xx")` | backend / reason / remediation |
| FTD3 | context compatibility | `Ftd3CommandContext` | `context` が残る |
| reason enum | discovery/error shared values | `CaptureReason` | local_029 と同じ reason を参照 |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| open failure logging | structured fields を UI log へ渡す | fake backend | 文字列解析不要 |
| docs example | `except CaptureError as exc` | 実機なし | `exc.code` で分岐できる |

### 検証コマンド

```console
uv run pytest tests/unit/test_structured_capture_errors.py
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

## 6. 実装チェックリスト

- [x] `CaptureError` に common fields を追加する。
- [x] discovery と error で共有する `CaptureReason` を定義する。
- [x] subclass default code / recoverable を固定する。
- [x] dependency / backend / device path から profile / backend context を渡す。
- [x] `Ftd3CommandError.context` の互換を維持する。
- [x] docs/api に structured error の例を追加する。
- [x] unit test と static gate を実行する。

## 7. 実装結果

### 7.1 Gate Results

| gate | result | evidence |
| ---- | ------ | -------- |
| Structured error unit | pass | `uv run pytest tests/unit/test_structured_capture_errors.py -q`: 8 passed。 |
| Related unit | pass | `uv run pytest tests/unit/test_structured_capture_errors.py tests/unit/test_high_level_capture_read_api.py tests/unit/test_ftd3_pipe_payloads.py tests/unit/test_n3dsxl_session.py tests/unit/test_n3dsxl_connect_sequence.py -q`: 45 passed。 |
| Static | pass | `uv run ruff format --check .`、`uv run ruff check .`、`uv run ty check --no-progress`。 |
| Hardware | not applicable | 例外 metadata の追加のみで、USB command は送信しない。 |

### 7.2 Deferred To `local_029`

`src/ponkan/devices/discovery.py` は `local_029` の対象として新規作成する。今回の完了条件は、discovery が import する共有 reason enum として `ponkan.errors.CaptureReason` を確定することに留めた。
