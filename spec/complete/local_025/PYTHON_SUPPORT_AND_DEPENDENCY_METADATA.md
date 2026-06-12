# Python Support and Dependency Metadata 仕様書

## 1. 概要

### 1.1 目的

`ponkan-python` の package metadata を、現在の実行経路と alpha 版の互換性方針に合わせて整理する。Python version の上限指定を外し、Windows D3XX backend で実際に必要な PyD3XX を通常依存へ移す。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| `requires-python` | package installer が参照する Python version 制約。 |
| 上限指定 | `requires-python` に含まれる `<3.14` のような future Python を拒否する条件。 |
| environment marker | dependency を OS や Python 実行環境に応じて解決する PEP 508 marker。 |
| optional extra | `ponkan-python[image]` のように利用者が明示して追加する dependency group。 |
| D3XX backend | FTDI D3XX driver 経由で new 3DS XL capture board を開く backend。 |
| PyD3XX | `D3xxBackend` が device enumeration、open、pipe operation、DLL / handle 取得に使う Python binding。 |

### 1.3 背景・問題

現行 metadata は `requires-python = ">=3.12, <3.14"` としているが、現時点で Python 3.14 以降を install metadata で拒否する明確な根拠はない。Python 3.12+ 構文を使う方針は維持しつつ、未検証の future Python は `Requires-Python` ではなく検証済み classifier、README、CI 対象で表す。

現行 metadata は `d3xx` extra に `pyd3xx>=1.1.4` を置いている。一方で high-level API の hardware path は `D3xxBackend()` を構築し、PyD3XX を lazy import する。`D3xxNativeApi` は自前の DLL calling convention wrapper だが、通常構築では PyD3XX-backed handle から DLL と `FT_HANDLE` を取り出しているため、PyD3XX の代替ではない。Windows の通常利用者に `ponkan-python[d3xx]` を要求するより、Windows marker 付き通常依存にする方が実行経路と一致する。

この repo は pre-alpha / alpha 相当であり、`d3xx` extra を互換 alias として残さない。古い install command は README と docs から削除する。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| Future Python install | `<3.14` により Python 3.14+ を metadata で拒否する | `>=3.12` のみで、未検証 version は runtime / test / docs で扱う |
| Windows D3XX dependency | 利用者が `ponkan-python[d3xx]` を明示しないと PyD3XX が入らない | Windows 通常 install で PyD3XX が解決される |
| Non-Windows dependency | `d3xx` extra を指定すると PyD3XX が解決され得る | 通常 install では PyD3XX を入れず、D3XX backend は unsupported / unavailable として扱う |
| Extra surface | `image` / `opencv` / `d3xx` | `image` / `opencv` のみ |
| Error guidance | PyD3XX missing 時も `d3xx` extra を案内する | extra で解決できる依存不足と通常依存の availability error を別の例外で表す |

### 1.5 着手条件

- [x] 作業ブランチ `chore/python-support-optional-deps` 上にいる。
- [x] `D3xxBackend` が PyD3XX を lazy import する現行経路を確認した。
- [x] `D3xxNativeApi` が PyD3XX-backed handle から DLL / handle を得る現行経路を確認した。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `pyproject.toml` | 修正 | `requires-python` から `<3.14` を削除し、`pyd3xx>=1.1.4; sys_platform == "win32"` を通常 dependency に移す。`d3xx` optional extra は削除する。 |
| `uv.lock` | 修正 | `pyproject.toml` の metadata 変更に合わせて lock を再生成する。 |
| `README.md` | 修正 | Python 対象表記、install command、D3XX backend dependency の説明を更新し、`ponkan-python[d3xx]` を削除する。 |
| `docs/api.md` | 修正 | API docs の install command と optional dependency 説明を更新する。 |
| `docs/publishing.md` | 修正 | publish / smoke command から `ponkan-python[d3xx]` を削除し、Windows marker 付き通常依存前提の確認手順に更新する。 |
| `src/ponkan/errors.py` | 修正 | 通常依存または platform-gated dependency の availability error 用に `DependencyUnavailableError` を追加し、`OptionalDependencyError` は extra 専用の意味に保つ。 |
| `src/ponkan/transport/d3xx_backend.py` | 修正 | PyD3XX import missing 時は `DependencyUnavailableError` を送出し、`d3xx` extra 前提の guidance を削除する。 |
| `tests/unit/test_d3xx_backend.py` | 修正 | PyD3XX missing error の例外型と期待 message を更新する。 |
| `tests/unit/test_layout_3ds_decoder.py` | 修正なし予定 | Pillow missing behavior が `image` extra 案内として維持されることを確認する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| Python 3.14+ の install metadata | Installer が package metadata を読む | `Requires-Python: >=3.12` により metadata だけでは拒否しない | Python 3.14 の動作保証を意味しない |
| Windows 通常 install | `pip install ponkan-python` on `sys_platform == "win32"` | `pyd3xx>=1.1.4` が通常 dependency として解決される | arch marker は付けない |
| Non-Windows 通常 install | `pip install ponkan-python` on non-Windows | PyD3XX は marker により解決対象外になる | D3XX backend は runtime unavailable |
| 旧 D3XX extra | `pip install "ponkan-python[d3xx]"` | extra は package metadata に存在しない | alpha 版の breaking cleanup として互換 alias を残さない |
| PyD3XX missing | Windows で marker 対象だが PyD3XX import 不可 | `DependencyUnavailableError` で通常 dependency 不足または unsupported environment を示す | `d3xx` extra を案内しない |
| Pillow missing | `to_pillow()` / PNG write path で Pillow import 不可 | `image` extra を案内する error を維持する | D3XX 方針変更の非対象 |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | PyD3XX missing error が `DependencyUnavailableError` になる | unit | 3.1 | `tests/unit/test_d3xx_backend.py` |
| green | PyD3XX missing error が `d3xx` extra を案内しない | unit | 3.1 | `tests/unit/test_d3xx_backend.py` |
| green | Pillow missing error は `image` extra 案内を維持する | unit | 3.1 | `tests/unit/test_layout_3ds_decoder.py` |
| green | lock metadata に `requires-python = ">=3.12"` が反映される | integration | 3.1 | `uv.lock` line 3 |
| green | package metadata の optional extras が `image` / `opencv` のみになる | integration | 3.1 | `uv.lock` `provides-extras = ["image", "opencv"]` |

### 3.3 設計方針

`requires-python` は下限だけを宣言する。未検証 Python version への注意は docs と CI matrix で扱い、install metadata の上限で future version を拒否しない。

PyD3XX は optional feature dependency ではなく、Windows の N3DSXL D3XX path の runtime dependency とする。dependency marker は OS に限定し、arch marker は付けない。64-bit DLL や driver mismatch は PyD3XX / D3XX runtime の availability として実行時 error で扱う。

`d3xx` extra は削除する。pre-alpha / alpha 版の metadata cleanup として互換 alias は残さず、古い install command は docs から消す。

`OptionalDependencyError` の意味は拡張しない。Pillow など本当に extra で解決する dependency だけを表す例外として残す。

PyD3XX のように通常 dependency / platform marker / unsupported platform の問題として扱う dependency には、新しい `DependencyUnavailableError` を使う。これにより、extra 追加で解決できる問題と、install target / platform / dependency omission の問題を API 上も文言上も混同しない。

## 4. 実装仕様

`pyproject.toml` の dependency metadata は次の形にする。

```toml
requires-python = ">=3.12"

dependencies = [
    "libusb1>=3.3.1",
    "numpy>=2.0",
    "pyd3xx>=1.1.4; sys_platform == 'win32'",
]

[project.optional-dependencies]
image = [
    "pillow>=10.0",
]
opencv = [
    "opencv-python>=4.10",
]
```

`d3xx` extra は定義しない。`README.md` と `docs/api.md` の install 例は次の方向へ変更する。

```console
pip install ponkan-python
pip install "ponkan-python[image]"
```

OpenCV を明示する箇所では `opencv` extra を残す。

```console
pip install "ponkan-python[opencv]"
```

PyD3XX missing 時の error は `OptionalDependencyError` ではなく、通常依存と platform 条件を示す `DependencyUnavailableError` にする。

```python
raise DependencyUnavailableError(
    "PyD3XX is required for the Windows D3XX backend. "
    "Install ponkan-python with dependencies on Windows, or use a supported backend."
)
```

`OptionalDependencyError("Pillow", "image")` は従来通り有効にする。`OptionalDependencyError` は `DependencyUnavailableError` の subclass にしてもよいが、PyD3XX missing path は `OptionalDependencyError` として扱わない。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| `load_pyd3xx_binding()` | PyD3XX missing error の型と文言 | import が常に `ImportError` | `DependencyUnavailableError` で `d3xx extra` を案内しない |
| `CaptureFrame.to_pillow()` | Pillow missing error の文言 | PIL import unavailable | `image` extra 案内を維持する |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| lock refresh | package metadata 反映 | `uv lock` 実行 | `uv.lock` の project metadata が `>=3.12` と Windows marker 付き PyD3XX dependency になる |
| package metadata review | optional extras の整理 | lock または build metadata 確認 | `d3xx` extra が存在しない |
| docs review | install command 更新 | README / docs grep | `ponkan-python[d3xx]` が残らない |

### 検証コマンド

```console
uv lock
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit/test_d3xx_backend.py tests/unit/test_layout_3ds_decoder.py -q
rg -n "ponkan-python\\[d3xx\\]|d3xx extra" README.md docs pyproject.toml
git diff --check
```

実機 new 3DS XL command はこの Work Unit では実行しない。dependency metadata と error / docs の整理であり、USB command scope はない。

## 6. 実装チェックリスト

- [x] `pyproject.toml` の `requires-python` と dependencies / optional dependencies を更新する。
- [x] `uv lock` を実行して `uv.lock` を更新する。
- [x] README / docs の install command と dependency 説明を更新する。
- [x] `DependencyUnavailableError` を追加し、PyD3XX missing error を通常依存化後の実態に合わせる。
- [x] unit test を更新する。
- [x] 検証コマンドを実行し、結果を仕様書へ反映する。
- [x] レビュー完了。

## 7. 実装結果

### 7.1 変更結果

| 項目 | 結果 |
| ---- | ---- |
| Python metadata | `requires-python = ">=3.12"` に変更し、Python 3.14+ を install metadata だけでは拒否しない。 |
| PyD3XX dependency | `pyd3xx>=1.1.4; sys_platform == 'win32'` を通常 dependency に移動した。 |
| optional extras | `d3xx` extra を削除し、`image` / `opencv` のみを残した。 |
| error surface | `DependencyUnavailableError` を追加し、PyD3XX missing path は `OptionalDependencyError` ではなくこの例外を送出する。 |
| docs | README / API docs / publishing smoke から `ponkan-python[d3xx]` を削除した。 |

### 7.2 Gate 結果

| gate | 結果 | evidence |
| ---- | ---- | -------- |
| lock refresh | pass | `uv lock`: Resolved 17 packages。`uv.lock` は `requires-python = ">=3.12"`、`pyd3xx` は `sys_platform == 'win32'` marker、`provides-extras = ["image", "opencv"]`。 |
| targeted unit | pass | `uv run pytest tests/unit/test_d3xx_backend.py tests/unit/test_layout_3ds_decoder.py -q`: 19 passed, 1 warning。 |
| unit | pass | `uv run pytest tests/unit -q`: 124 passed, 1 warning。 |
| format | pass | `uv run ruff format --check .`: 70 files already formatted。 |
| lint | pass | `uv run ruff check .`: All checks passed。 |
| type | pass | `uv run ty check --no-progress`: All checks passed。 |
| docs grep | pass | `rg -n "ponkan-python\\[d3xx\\]|d3xx extra" README.md docs pyproject.toml`: no matches。 |
| lock grep | pass | `rg -n "extra == 'd3xx'" uv.lock`: no matches。 |
| whitespace | pass | `git diff --check`: no output。 |
| hardware | not applicable | 実機 command scope はない。 |

`uv run ...` 実行時に `.venv\Lib\site-packages\ponkan_python-0.1.0.dist-info` の `RECORD` missing による uninstall warning が出たが、各 command は成功した。これは既存 editable install 周辺の環境 warning であり、本 Work Unit の gate failure ではない。
