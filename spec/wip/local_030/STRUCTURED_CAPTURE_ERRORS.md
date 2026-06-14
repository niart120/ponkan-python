# Structured Capture Errors 仕様書

更新日: 2026-06-14

## 1. 概要

### 1.1 目的

`CaptureError` hierarchy に `code`、`profile`、`backend`、`reason`、`recoverable`、`remediation` を持たせ、GUI や adapter が例外メッセージ文字列を解析せずに user log / status bar / technical log を分けられるようにする。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| error code | 例外種別を機械的に識別する stable string。例: `device_not_found`。 |
| reason | 同じ error code 内で原因を絞る string。例: `missing_driver`。 |
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

- [ ] 現行 `src/ponkan/errors.py` の exception hierarchy を確認する。
- [ ] `local_029` の device discovery reason と命名を合わせる。
- [ ] 既存 unit test が例外メッセージに依存していないか確認する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_030/STRUCTURED_CAPTURE_ERRORS.md` | 新規 | structured error model の仕様を定義する。 |
| `src/ponkan/errors.py` | 修正 | `CaptureError` common fields と subclass default を追加する。 |
| `src/ponkan/capture.py` | 修正 | profile / backend context を例外生成時に渡す。 |
| `src/ponkan/devices/discovery.py` | 修正 | discovery reason と error reason の命名を揃える。 |
| `src/ponkan/devices/n3dsxl_ftd3.py` | 修正 | rejected / unreadable / open failure context を structured にする。 |
| `docs/api.md` | 修正 | structured errors の扱いを追記する。 |
| `tests/unit/test_structured_capture_errors.py` | 新規 | fields、string compatibility、subclass defaults を検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| base error | `CaptureError(...)` | common fields を持つ | message は従来通り str で見える |
| device not found | device 候補なし | `code="device_not_found"`, `recoverable=True` | source は表示し未接続 status にできる |
| unsupported profile | unknown profile | `code="unsupported_profile"` | 通常 UI 非表示 |
| missing package | PyD3XX missing | `code="dependency_unavailable"`, `reason="missing_package"` | remediation 付き |
| device rejected | VID/PID/product string 不一致 | `code="device_rejected"` | safety warning |
| read failed | streaming read error | `code="read_failed"` | reconnect candidate |
| decode failed | raw decode error | `code="decode_failed"` | technical log |
| FTD3 context | command failure | 既存 `context` を維持し common fields も持つ | backward compatible |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | `CaptureError` は common fields を持つ | new behavior | 3.1 | default values |
| todo | subclass は stable default `code` を持つ | contract | 3.1 | `DeviceNotFound` など |
| todo | `str(error)` は既存 message と互換 | regression | 3.1 | user-visible text |
| todo | `DependencyUnavailableError.for_backend_dependency` は `reason="missing_package"` と backend context を持つ | diagnostics | 3.1 | backend field |
| todo | `Ftd3CommandError.context` は維持される | regression | 3.1 | existing tests |
| todo | error fields は JSON log に変換しやすい | integration | 3.1 | `to_dict()` optional |

### 3.3 設計方針

既存 exception class 名は維持する。利用側が `except DeviceNotFound` のように分岐している可能性があるため、class hierarchy の破壊はしない。

common fields は constructor kwargs で渡せるようにし、subclass は default `code` / `recoverable` を持つ。`Ftd3CommandError` の `context` は削除せず、common fields の `details` または `technical_context` として参照できるようにする。

## 4. 実装仕様

```python
class CaptureError(Exception):
    code: str
    profile: str | None
    backend: str | None
    reason: str | None
    recoverable: bool
    remediation: str | None

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        profile: str | None = None,
        backend: str | None = None,
        reason: str | None = None,
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

- [ ] `CaptureError` に common fields を追加する。
- [ ] subclass default code / recoverable を固定する。
- [ ] dependency / backend / device path から profile / backend context を渡す。
- [ ] `Ftd3CommandError.context` の互換を維持する。
- [ ] docs/api に structured error の例を追加する。
- [ ] unit test と static gate を実行する。
