# Backend Capability Resolution 仕様書

更新日: 2026-06-14

## 1. 概要

### 1.1 目的

`ponkan` に backend availability を軽量に判定する public API を追加し、利用側が `open_capture()` より前に backend preference、runtime dependency、driver、platform、device enumeration の状態を機械的に判断できるようにする。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| backend preference | 利用者が指定する backend 候補。`auto`、`d3xx`、`d3xx-native`、`libusb`。 |
| resolved backend | `auto` などの preference から実際に選ばれる backend。 |
| capability check | device command を送らずに、package / backend module / driver / lightweight enumeration の状態を調べる処理。 |
| unavailable reason | `missing_package`、`missing_driver`、`missing_runtime`、`unsupported_platform`、`device_not_found` などの機械判定用理由。 |
| remediation | 利用者に提示できる短い復旧案内。 |

### 1.3 背景・問題

現行の利用側は `importlib.util.find_spec("ponkan")` で package availability だけを判定できる。しかし、実際に capture source を使えるかは D3XX binding、Windows driver service、platform、backend choice、device visibility に依存する。`open_capture()` まで進めると N3DSXL command boundary に近づくため、GUI menu 構築や設定画面ではより軽量な判定が必要である。

この仕様では、backend capability API は N3DSXL command を送らない。device enumeration を行う場合も descriptor 取得までに留め、明示的な open / connect は `open_capture()` の責務とする。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| package 判定 | import 可否のみ | backend ごとの availability を返す |
| `auto` の説明 | docs を読む必要がある | `resolve_backend("auto")` で resolved backend を得る |
| driver mismatch | `open_capture()` 失敗まで不明 | capability と reason で事前に warning できる |
| UI 表示 | source を隠すか warning かを利用側が推測 | `available` と `reason` で分岐できる |
| 実機安全 | capability check の command scope が曖昧 | command 送信なしを contract にする |

### 1.5 着手条件

- [ ] `local_028` の profile registry が実装済み、またはこの仕様内で profile id は文字列として暫定扱いできる。
- [ ] 現行 high-level `auto` が D3XX path を選ぶ事実を確認する。
- [ ] `d3xx-native` を default 化しない既存判断を維持する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_029/BACKEND_CAPABILITY_RESOLUTION.md` | 新規 | backend capability / resolver の仕様を定義する。 |
| `src/ponkan/backends.py` | 新規 | backend capability 型と resolver API を追加する。 |
| `src/ponkan/capture.py` | 修正 | `open_capture()` の backend validation と resolver を共通化する。 |
| `src/ponkan/errors.py` | 修正 | capability API 用の structured reason を必要に応じて追加する。 |
| `src/ponkan/__init__.py` | 修正 | `resolve_backend()` と `get_backend_capabilities()` を export する。 |
| `docs/api.md` | 修正 | backend capability check の例を追加する。 |
| `tests/unit/test_backend_capabilities.py` | 新規 | lightweight resolver と failure reason を検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| auto を解決する | `resolve_backend("auto", profile="n3dsxl")` | 現行 high-level default と同じ backend を返す | 初期は `d3xx` |
| 明示 backend を解決する | `resolve_backend("d3xx-native")` | `d3xx-native` を返す | silent fallback しない |
| unsupported backend を扱う | `resolve_backend("libusb", profile="n3dsxl")` | high-level unsupported を reason 付きで返す | 現行 `open_capture` と整合 |
| capability 一覧を返す | `get_backend_capabilities(profile="n3dsxl")` | backend ごとの availability を返す | command 送信なし |
| missing dependency | PyD3XX import 不可 | `available=False`, `reason="missing_package"` | remediation 付き |
| unsupported platform | backend が OS 非対応 | `reason="unsupported_platform"` | platform 判定 |
| device not found | lightweight enumeration で候補なし | `reason="device_not_found"` | enumeration を実施する mode のみ |
| command を送らない | capability check | N3DSXL connect / stream setup を実行しない | safety boundary |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | `resolve_backend("auto", "n3dsxl")` は現行 default を返す | contract | 3.1 | default resolver 固定 |
| todo | 明示 `d3xx-native` は fallback しない | safety | 3.1 | unavailable でも resolved は明示 backend |
| todo | unsupported backend は reason を返す | edge | 3.1 | `libusb` high-level path |
| todo | dependency missing を structured reason にする | error | 3.1 | import monkeypatch |
| todo | capability check は N3DSXL command を送らない | safety | 3.1 | fake backend spy |
| todo | package root export が成立する | public surface | 2 | `from ponkan import resolve_backend` |

### 3.3 設計方針

capability API は「起動時や設定画面で安全に呼べる診断」とする。`open_capture()` の代替ではないため、device を開いて command sequence を流す確認はしない。device presence を含める場合も descriptor enumeration までに留める。

`auto` の resolver は利用者ログに出せるようにするが、backend 選択ポリシーを不用意に変えない。Windows で `auto` を将来 `d3xx-native` 優先へ変える場合は、この仕様の実装とは別に release note / migration note を必要条件とする。

## 4. 実装仕様

```python
from dataclasses import dataclass
from typing import Literal

BackendPreference = Literal["auto", "d3xx", "d3xx-native", "libusb"]
BackendAvailabilityReason = Literal[
    "available",
    "missing_package",
    "missing_driver",
    "missing_runtime",
    "unsupported_platform",
    "unsupported_backend",
    "device_not_found",
    "unknown",
]


@dataclass(frozen=True, slots=True)
class BackendCapability:
    backend: str
    profile_id: str
    available: bool
    reason: BackendAvailabilityReason
    remediation: str | None
    opens_device: bool
    sends_device_commands: bool
    details: dict[str, object]


@dataclass(frozen=True, slots=True)
class ResolvedBackend:
    preference: BackendPreference
    backend: str
    profile_id: str
    available: bool
    reason: BackendAvailabilityReason
    remediation: str | None
```

Public API:

```python
def resolve_backend(
    preference: BackendPreference = "auto",
    *,
    profile: str = "n3dsxl",
    require_available: bool = False,
) -> ResolvedBackend:
    ...


def get_backend_capabilities(
    *,
    profile: str = "n3dsxl",
    include_device_presence: bool = False,
) -> tuple[BackendCapability, ...]:
    ...
```

`include_device_presence=False` では import / platform / runtime check までに留める。`True` の場合も N3DSXL command は送らず、device descriptor enumeration だけを行う。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| resolver | auto default | `auto`, `n3dsxl` | `backend == "d3xx"` |
| resolver | explicit native | `d3xx-native` | fallback しない |
| resolver | invalid backend | `bogus` | `ValueError` または `CaptureError` |
| capability | missing dependency | import failure | reason が `missing_package` |
| capability | unsupported high-level libusb | `libusb` | `available=False` |
| safety | command spy | fake protocol | connect が呼ばれない |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| docs example | capability API の import と表示 | 実機なし | backend 状態を JSON 化できる |
| open path consistency | `open_capture(backend="auto")` と resolver | 実機なし / fake opener | default backend policy が一致する |

### 検証コマンド

```console
uv run pytest tests/unit/test_backend_capabilities.py
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

## 6. 実装チェックリスト

- [ ] backend capability 型を定義する。
- [ ] `resolve_backend()` を現行 high-level default と一致させる。
- [ ] `get_backend_capabilities()` を command 送信なしで実装する。
- [ ] dependency / platform / unsupported reason を structured にする。
- [ ] `open_capture()` の backend validation と重複しないように整理する。
- [ ] docs/api に capability check 例を追加する。
- [ ] unit test と static gate を実行する。
