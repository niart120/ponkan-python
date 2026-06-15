# Exception Failure Public Contract 仕様書

更新日: 2026-06-15

## 1. 概要

### 1.1 目的

`ponkan` の例外・失敗経路に関する public contract を拡充し、GUI / adapter が例外型と文字列だけに依存せず、D3XX backend failure と profile / layout 解決失敗を機械的に扱えるようにする。

この仕様では、`D3xxBackendError` の structured fields を `CaptureError` 共通 field と整合させ、`UnknownCaptureProfile` / `UnknownCaptureLayout` を package root から import できる public error surface として扱う。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| backend failure | D3XX native API call、descriptor parse、candidate validation など backend 層で発生する失敗。 |
| public error surface | 利用側が documented import として参照できる例外型・属性。 |
| common structured fields | `CaptureError` が持つ `code`、`profile`、`backend`、`reason`、`recoverable`、`remediation`。 |
| backend-specific context | `D3xxBackendError.function`、`status`、`field_name` のような技術ログ向け詳細。 |
| root export | `from ponkan import ...` で import できる package root の公開 API。 |

### 1.3 背景・問題

`local_030` で `CaptureError` に common structured fields が追加されたが、`D3xxBackendError` は現状 base default の `code="capture_error"` のままで、D3XX API failure と descriptor parse failure を GUI が安定して分類しにくい。

また `UnknownCaptureProfile` と `UnknownCaptureLayout` は docs で public error として説明されている一方、package root には export されていない。利用側は `ponkan.profiles` / `ponkan.layouts` を知っていれば import できるが、root の public API としての discoverability は低い。

`list_capture_devices()` の D3XX API failure を result object に畳む設計は関連するが、API の throw / no-throw 方針を変えるため別判断が必要である。この件は `spec/dev-journal.md` に先送り記録し、この仕様の即時対象から外す。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| D3XX backend failure の分類 | `code="capture_error"` と backend-specific 属性を利用側が独自解釈する | `code` / `reason` / `backend` で最低限分類でき、詳細は `function` / `status` / `field_name` で読む |
| root import | profile / layout unknown errors は submodule import が必要 | `from ponkan import UnknownCaptureProfile, UnknownCaptureLayout` が成立する |
| GUI / adapter 実装 | exception message か submodule path に依存しやすい | public root error surface と structured fields で分岐できる |
| release docs | D3XX failure と unknown profile/layout の扱いが散る | API Reference に error import と field contract をまとめる |

### 1.5 着手条件

- [x] `local_030` の `CaptureError` common structured fields が実装済みである。
- [x] `D3xxBackendError` が `function` / `status` / `field_name` を持つことを確認済みである。
- [x] `UnknownCaptureProfile` / `UnknownCaptureLayout` が `CaptureError` subclass として実装済みである。
- [x] D3XX discovery result-object 化は本仕様の対象外として dev-journal に分離する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_033/EXCEPTION_FAILURE_PUBLIC_CONTRACT.md` | 新規 | 例外・失敗経路の public contract 拡充仕様を定義する。 |
| `src/ponkan/transport/d3xx_backend.py` | 修正 | `D3xxBackendError` に stable `code` / `reason` / `backend` を付与する。 |
| `src/ponkan/__init__.py` | 修正 | `UnknownCaptureProfile` / `UnknownCaptureLayout` を root export に追加する。 |
| `src/ponkan/profiles.py` | 既存利用 | `UnknownCaptureProfile` の structured fields を維持する。 |
| `src/ponkan/layouts.py` | 既存利用 | `UnknownCaptureLayout` の structured fields を維持する。 |
| `docs/api.md` | 修正 | root import と D3XX backend failure の structured contract を追記する。 |
| `tests/unit/test_structured_capture_errors.py` | 修正 | D3XX backend error の common fields と backend-specific context を検証する。 |
| `tests/unit/test_package.py` | 修正 | root export の public import surface を検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| D3XX API failure を生成する | `D3xxBackendError("FT_Create", 1)` | `code="d3xx_backend_failed"`、`backend="d3xx"`、`reason="open_failed"`、`function="FT_Create"`、`status=1` | open/configure 系 call |
| D3XX descriptor parse failure を生成する | `D3xxBackendError.missing_field("Description")` | `code="d3xx_backend_failed"`、`reason="read_failed"`、`field_name="Description"` | descriptor enumeration / parse |
| invalid candidate を生成する | `D3xxBackendError.invalid_candidate()` | stable code と `function="invalid candidate"` を持つ | caller misuse / stale candidate |
| root から profile unknown error を import する | `from ponkan import UnknownCaptureProfile` | import でき、`ponkan.__all__` に含まれる | submodule import は維持 |
| root から layout unknown error を import する | `from ponkan import UnknownCaptureLayout` | import でき、`ponkan.__all__` に含まれる | submodule import は維持 |
| existing message compatibility | 既存 error message を読む | `str(error)` は従来形式を維持する | user-visible text を壊さない |
| docs の catch-all 例 | `except CaptureError as exc` | `exc.to_dict()` に D3XX common fields が含まれる | backend-specific 属性は `hasattr` / `isinstance` で読む |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | `D3xxBackendError("FT_Create", 1)` は stable common fields と D3XX context を持つ | new behavior | 3.1 | `test_structured_capture_errors.py` |
| todo | `D3xxBackendError.missing_field(...)` は field context と structured fields を持つ | new behavior | 3.1 | descriptor parse failure |
| todo | `str(D3xxBackendError(...))` は既存 message format を維持する | regression | 3.1 | docs / logs 互換 |
| todo | `UnknownCaptureProfile` / `UnknownCaptureLayout` を package root から import できる | public surface | 3.1 | `test_package.py` |
| todo | `ponkan.__all__` に unknown error 型が含まれる | public surface | 3.1 | root export |
| todo | API docs の root import 例に unknown error 型が含まれる | docs contract | 3.1 | release docs |

### 3.3 設計方針

`D3xxBackendError` は `CaptureError` subclass として common structured fields を使い、backend-specific context は既存属性として残す。`function` / `status` / `field_name` は technical log 用であり、UI の primary branch は `code` / `reason` / `backend` を使う。

`reason` は call site ごとに完全分類しすぎない。D3XX API call / descriptor parse の多くは backend が見えていても capture open 前後の low-level failure であるため、初期値は `open_failed` または `read_failed` に限定する。詳細分類が必要になった場合は別 Work Unit で `CaptureReason` を増やす。

root export は `UnknownCaptureProfile` と `UnknownCaptureLayout` に限定する。`SupportStatus`、`BackendPreference` などの typing alias は root に追加しない。runtime value ではなく型補助の性格が強く、root surface を広げすぎるためである。

`list_capture_devices()` の D3XX API failure を `CaptureDeviceDiscovery` result に畳む設計は、この仕様では扱わない。no-throw discovery API へ寄せるかどうかは、呼び出し側の error-handling policy と一緒に決める。

## 4. 実装仕様

```python
class D3xxBackendError(CaptureError):
    def __init__(
        self,
        function: str,
        status: int | None = None,
        *,
        field_name: str | None = None,
        reason: CaptureReason = "open_failed",
    ) -> None:
        super().__init__(
            _d3xx_error_message(function, status, field_name),
            code="d3xx_backend_failed",
            backend="d3xx",
            reason=reason,
            recoverable=True,
        )
        self.function = function
        self.status = status
        self.field_name = field_name
```

factory method の reason:

| factory / path | reason |
| -------------- | ------ |
| `D3xxBackendError(function, status)` | `open_failed` |
| `missing_field(field_name)` | `read_failed` |
| `invalid_integer(field_name)` | `read_failed` |
| `invalid_candidate()` | `open_failed` |

root export:

```python
from ponkan.layouts import UnknownCaptureLayout
from ponkan.profiles import UnknownCaptureProfile

__all__ = [
    ...,
    "UnknownCaptureLayout",
    "UnknownCaptureProfile",
]
```

docs には次を追記する。

- top-level import example に `UnknownCaptureProfile` / `UnknownCaptureLayout` を追加する。
- Error Types に `D3xxBackendError` の stable `code` / `reason` / backend-specific context を明記する。
- `D3xxBackendError` は root export しない。transport-specific error として `ponkan.transport.d3xx_backend` から import する。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| `D3xxBackendError` | common fields | `D3xxBackendError("FT_Create", 1)` | `code="d3xx_backend_failed"`、`backend="d3xx"` |
| `D3xxBackendError` | backend-specific context | `D3xxBackendError.missing_field("ID")` | `field_name="ID"`、message 維持 |
| root export | profile unknown error | `from ponkan import UnknownCaptureProfile` | import 成功 |
| root export | layout unknown error | `from ponkan import UnknownCaptureLayout` | import 成功 |
| `__all__` | public surface | `ponkan.__all__` | unknown error 型が含まれる |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| GUI-style error logging | common fields と D3XX context を technical log に渡す | fake D3XX error | message 文字列解析なしで分類できる |
| API docs import example | top-level import 例の成立 | 実機なし | root import が成立する |

### 検証コマンド

```console
uv run pytest tests/unit/test_structured_capture_errors.py tests/unit/test_package.py
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
git diff --check
```

## 6. 実装チェックリスト

- [ ] `D3xxBackendError` の common structured fields を実装する。
- [ ] factory method ごとの `reason` を固定する。
- [ ] `UnknownCaptureProfile` / `UnknownCaptureLayout` を package root に export する。
- [ ] API docs の root import と Error Types を更新する。
- [ ] unit test を追加・更新する。
- [ ] ruff / ty / pytest / diff check を実行する。
