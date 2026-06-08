# API Docstring 拡充 仕様書

## 1. 概要

### 1.1 目的

`py3dscapture` の公開 API と backend 境界の docstring を拡充し、利用者が引数、戻り値、例外、side effect、実機安全境界を実装本文まで読まずに判断できる状態にする。実行時の振る舞いは変更せず、既存の Google style docstring 運用に合わせる。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| 公開 API | `src/py3dscapture` 配下の非 private module / class / function / method のうち、利用者、CLI、test double、backend 実装が直接呼び出す可能性がある surface。 |
| backend 境界 | `Protocol`、transport adapter、device session など、実機 USB backend や fake backend が満たす contract。 |
| Google style docstring | `pyproject.toml` の `tool.ruff.lint.pydocstyle.convention = "google"` に従う docstring 形式。 |
| 1 行 docstring | summary だけで、引数、戻り値、例外、side effect、前提条件の説明を持たない docstring。 |
| 実機安全境界 | N3DSXL command を送れる device identity、product string、approval flag、artifact 保存、cleanup に関する制約。 |

### 1.3 背景・問題

既存の Ruff `D` rule は docstring の存在と基本形式を検査できるが、説明の十分性までは検査しない。そのため、`RawCapture`、`CaptureFrame`、`StreamingEngine`、`Ftd3Pipe`、`N3DSXLProtocol`、device discovery、transport backend などに、summary だけの docstring が残っている。

特にこの repo は実機 new 3DS XL capture board へ USB command を送るため、API 利用者が「どの引数が byte length か」「どの pipe / endpoint を渡すのか」「どの例外が安全境界違反や decode failure を示すのか」「callback 内で何をしてはいけないのか」を docstring から確認できる必要がある。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| 引数説明 | 型注釈のみ、または summary に暗黙化 | 引数を持つ公開 API は `Args:` か本文で意味と単位を説明する |
| 戻り値説明 | `Return ...` の 1 行が中心 | 利用者が値の所有権、copy 有無、shape、byte length、metadata を判断できる |
| 例外説明 | 多くが本文から推測する状態 | public API の主要な `ValueError`、`DecodeError`、`UnsupportedDevice`、`DeviceOpenError`、`Ftd3CommandError` を説明する |
| 実機安全境界 | AGENTS / spec にはあるが API docstring には薄い | device / transport / protocol API の docstring に安全前提と cleanup を記載する |
| 検証 | `ruff check` が形式のみ確認 | `ruff format --check`、`ruff check`、`ty check`、unit test が通り、振る舞い変更がない |

### 1.5 着手条件

- [x] `pyproject.toml` で Google style docstring が採用済みである。
- [x] `src/py3dscapture` に API 対象の Python package が存在する。
- [x] 実機 command の安全制約は `AGENTS.md` と既存 `spec/complete` に記録済みである。
- [x] docstring 拡充対象の公開 API を実装前に一覧化する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_020/API_DOCSTRING_EXPANSION.md` | 新規 | API docstring 拡充の作業仕様を追加する |
| `src/py3dscapture/__init__.py` | 修正 | package の初期公開 surface と MVP 対象範囲を説明する |
| `src/py3dscapture/capture.py` | 修正 | `RawCapture`、`save_raw_capture`、`FrameEngine`、`CaptureSession` の引数、戻り値、例外、metadata contract を説明する |
| `src/py3dscapture/image/frame.py` | 修正 | `CaptureFrame` と画像変換 API の screen 名、colorspace、copy、Pillow optional dependency、shape 制約を説明する |
| `src/py3dscapture/protocol/sizes.py` | 修正 | size 計算 API の 2D / 3D mode、byte 単位、cc3dsfs 由来の 1024 byte alignment を説明する |
| `src/py3dscapture/protocol/layout_3ds.py` | 修正 | raw RGB8 2D decode API の入力長、layout、戻り値、`DecodeError` を説明する |
| `src/py3dscapture/protocol/n3dsxl.py` | 修正 | connect / raw frame read sequence の前提、非対象 3D mode、pipe contract、例外を説明する |
| `src/py3dscapture/devices/n3dsxl_ftd3.py` | 修正 | device classification、unreadable product string、session ownership、interface claim / release を説明する |
| `src/py3dscapture/transport/libusb_backend.py` | 修正 | libusb protocol と `Usb1Backend` の device identity、handle lifecycle、bulk read / write contract を説明する |
| `src/py3dscapture/transport/libusb_async.py` | 修正 | async transfer callback / backend contract、callback 内の禁止事項、placeholder 実装の gating を説明する |
| `src/py3dscapture/transport/ftd3_pipe.py` | 修正 | command payload builder と pipe wrapper の引数、byte order、command id、pipe / length validation、error context を説明する |
| `src/py3dscapture/transport/ftd3_backend.py` | 修正 | libusb 優先、D3XX fallback、backend mismatch 判定、transport lifecycle を説明する |
| `src/py3dscapture/transport/d3xx_backend.py` | 修正 | D3XX binding / device / handle / backend の候補列挙、open、pipe operation、status error を説明する |
| `src/py3dscapture/transport/d3xx_streaming.py` | 修正 | D3XX async backend の worker lifecycle、cancel / drain / release、callback contract を説明する |
| `src/py3dscapture/streaming/buffers.py` | 修正 | raw slot pool の所有権、memoryview、checkout / release contract を説明する |
| `src/py3dscapture/streaming/policies.py` | 修正 | bounded queue と drop policy の意味、callback thread での block 禁止を説明する |
| `src/py3dscapture/streaming/engine.py` | 修正 | streaming lifecycle、queue sizes、drop policy、decoder injection、shutdown contract を説明する |
| `src/py3dscapture/streaming/stats.py` | 修正 | counters と performance report の単位、snapshot、JSON serializable contract を説明する |
| `src/py3dscapture/artifacts.py` | 修正 | artifact path validation、overwrite policy、JSON artifact contract を説明する |
| `src/py3dscapture/hardware_gate.py` | 修正 | env flag 判定と hardware approval plan の意味、安全境界を説明する |
| `src/py3dscapture/errors.py` | 修正 | 公開例外 hierarchy、構造化 error context、optional dependency error の引数を説明する |
| `src/py3dscapture/tools/*.py` | 修正 | CLI から再利用される helper だけ、引数、出力 artifact、戻り値 status を説明する |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| 公開 API の説明拡充 | 引数を持つ公開 class / function / method | summary だけでなく、必要に応じて `Args:`、`Returns:`、`Raises:`、`Yields:`、`Attributes:` を持つ | 型注釈の単純な読み替えではなく、意味、単位、制約を書く |
| 実行時振る舞いの不変 | docstring だけを修正する | import、関数戻り値、例外型、test result が変わらない | docstring 内の example 追加は副作用を持たない形にする |
| 画像 API の利用判断 | `CaptureFrame.to_ndarray` / `to_pillow` / `to_mosaic` | screen 名、colorspace、copy、optional dependency、shape が docstring から分かる | ndarray の shape は `(height, width, 3)` と明記する |
| raw capture API の利用判断 | `RawCapture` / `save_raw_capture` | payload 範囲、metadata JSON、overwrite policy、返却 path が docstring から分かる | raw bytes と metadata の同一 stem contract を明記する |
| device / transport 安全境界 | device classification、session open、FTD3 / D3XX / libusb 操作 | accepted device 前提、unreadable product string の扱い、cleanup、送信 command scope が docstring から分かる | 安全制約は AGENTS と矛盾させない |
| streaming lifecycle の利用判断 | `StreamingEngine`、queue、buffer、stats | callback 内で decode しない設計、bounded queue、drop policy、stop cleanup が docstring から分かる | block policy と callback thread の関係を明記する |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | 公開 API docstring audit で対象一覧を固定する | static audit | 3.1 | AST helper で非 private class / function と 1 行 docstring を確認した |
| green | docstring 拡充後も Ruff docstring rule が通る | lint | 3.1 | `uv run ruff check .` |
| green | format 変更が Ruff formatter と衝突しない | format | 3.1 | `uv run ruff format --check .` |
| green | 型チェック結果が変わらない | type | 3.1 | `uv run ty check --no-progress` |
| green | unit test が既存振る舞い不変を確認する | regression | 3.1 | `uv run pytest tests/unit` |
| deferred | docstring の内容品質を自動 test 化する | documentation | 3.1 | 内容文面の test は brittle になりやすいため、必要なら key API の `__doc__` smoke に限定する |

### 3.3 設計方針

docstring は「利用者が次の呼び出しを安全に書けるか」を基準にする。型注釈で分かる `int` や `bytes` の再説明ではなく、byte 単位、USB pipe / endpoint、queue capacity、mode flag、metadata key、戻り値の copy / ownership、例外条件、cleanup responsibility を優先して書く。

対象は非 private API、`Protocol` による backend contract、CLI から再利用される helper を中心にする。先頭 underscore の private helper は原則として対象外とし、例外として command payload layout や error context の理解に必要な場合だけ簡潔な docstring を追加する。

原典 `cc3dsfs` 由来の command 値、構造体サイズ、sequence に新しい主張を追加する場合は、既存 spec または source audit に事実がある範囲だけを書く。未確認の推測を docstring に事実として書かない。

## 4. 実装仕様

docstring は Google style の次の粒度を目安にする。

```python
def save_raw_capture(
    capture: RawCapture,
    out_path: Path,
    *,
    force: bool = False,
) -> tuple[Path, Path]:
    """Save one raw capture payload and sidecar metadata file.

    The binary file uses ``out_path`` as-is. The metadata file is written next
    to it with the same stem and a ``.json`` suffix.

    Args:
        capture: Raw capture whose payload contains at least ``transferred`` bytes.
        out_path: Destination path for the raw binary payload.
        force: Overwrite an existing binary or metadata file when true.

    Returns:
        ``(bin_path, metadata_path)`` for the files written by this call.

    Raises:
        FileExistsError: Either destination already exists and ``force`` is false.
    """
```

class / dataclass docstring は、field が public contract を担う場合に `Attributes:` を使う。

```python
@dataclass(slots=True)
class CaptureFrame:
    """Decoded RGB8 capture frame.

    Attributes:
        top: Top screen image as ``uint8`` ndarray with shape ``(240, 400, 3)``.
        bottom: Bottom screen image as ``uint8`` ndarray with shape ``(240, 320, 3)``.
        top_right: Right-eye top screen in 3D mode, or ``None`` for 2D captures.
    """
```

公開 method の `Raises:` は、利用者が分岐できる例外だけを書く。private 実装 detail 由来の一時的な例外や、単に依存 library が投げる全例外を網羅しない。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| Ruff format | docstring の改行と indentation が formatter と衝突しない | `uv run ruff format --check .` | 成功 |
| Ruff lint | Google style docstring rule と既存 lint rule を満たす | `uv run ruff check .` | 成功 |
| ty | docstring 変更で import や型評価に副作用がない | `uv run ty check --no-progress` | 成功 |
| unit regression | docstring 変更前後で既存 unit behavior が変わらない | `uv run pytest tests/unit` | 成功 |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| CLI import | CLI helper の docstring 拡充後も module import と `main` 呼び出し test が壊れない | 実機なし | 既存 unit test が成功する |
| hardware gate | 実機 command の安全境界を docstring に書いても command 実行 path は変えない | 実機なし | 実機 test は未実行でよい |

### 検証コマンド

```console
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

実機検証は不要。docstring 変更で実機 command を実行しない。

検証結果:

```text
uv run ruff format . -> 61 files left unchanged
uv run ruff check . -> All checks passed!
uv run ty check --no-progress -> All checks passed!
uv run pytest tests/unit -> 88 passed
uv run ruff format --check . -> 61 files already formatted
```

## 6. 実装チェックリスト

- [x] API docstring 拡充仕様を `spec/wip/local_020` に作成する。
- [x] 公開 API と 1 行 docstring の現状を audit する。
- [x] `capture.py` と `image/frame.py` の利用者向け API docstring を拡充する。
- [x] `protocol/sizes.py`、`protocol/layout_3ds.py`、`protocol/n3dsxl.py` の protocol API docstring を拡充する。
- [x] `devices/n3dsxl_ftd3.py` の device classification / session API docstring を拡充する。
- [x] `transport/*` の backend boundary と FTD3 / D3XX API docstring を拡充する。
- [x] `streaming/*` の lifecycle、queue、buffer、stats API docstring を拡充する。
- [x] `artifacts.py` と `hardware_gate.py` の artifact / approval API docstring を拡充する。
- [x] `errors.py` の公開例外 docstring を拡充する。
- [x] CLI helper のうち再利用される API の docstring を必要範囲で拡充する。
- [x] docstring に新しい未検証 protocol 事実を書いていないことを確認する。
- [x] `uv run ruff format --check .` を実行する。
- [x] `uv run ruff check .` を実行する。
- [x] `uv run ty check --no-progress` を実行する。
- [x] `uv run pytest tests/unit` を実行する。
