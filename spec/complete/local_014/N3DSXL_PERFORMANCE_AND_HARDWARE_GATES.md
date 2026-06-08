# N3DSXL Performance And Hardware Gates 仕様書

更新日: 2026-06-08

追補: `spec/complete/local_015/N3DSXL_UNREADABLE_PRODUCT_STRING_POLICY.md` により、hardware gate の identity は product string と `product_string_status` を記録する。product string が読める場合の不一致拒否は継続し、読めない場合は accepted VID/PID と明示承認を safety boundary とする。

## 1. 概要

### 1.1 目的

Step 8 として、new 3DS XL 実機を使う E2E / performance smoke test の安全条件、pytest marker、承認境界、artifact、測定基準、報告形式を定義する。

この仕様は実装そのものではなく、実機を伴う gate を Agentic SDD が安全に扱うための operational spec である。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| Hardware Approval | 人間が device identity、command scope、安全理由、artifact、cleanup を確認し、実行を明示承認すること。 |
| `PONKAN_RUN_N3DSXL` | `requires_n3dsxl` test を実行する意図を示す環境変数。 |
| `PONKAN_RUN_PERFORMANCE` | performance marker の test を実行する意図を示す環境変数。 |
| `PONKAN_HARDWARE_APPROVED` | 実機 command を同じ command 内で許可する承認フラグ。 |
| Performance Smoke | 2D mode、no-op consumer、Pillow 変換なしで 60 秒 streaming し、fps/drop/error/shutdown を測る gate。 |
| Artifact | raw fixture、metadata、stats JSON、log、PNG、manual visual result など検証証拠。 |

### 1.3 背景・問題

N3DSXL command は実機 USB device へ送信されるため、CI や通常 unit test で暗黙実行してはいけない。Agentic SDD では local unit gate と hardware gate を分け、実機 gate は承認まで停止する必要がある。

performance smoke は MVP acceptance だが、実機、OS、USB controller、Python binding に依存する。初期目標は `delivered >= 50 fps` だが、初回測定後に source/hardware 状態とともに見直せるよう、stats と logs を残す。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| 実機 command | 個別判断 | marker、env var、human approval を必須にする |
| CI 安全 | 実装なし | CI で実機 test を実行しない |
| performance 証拠 | 未定 | stats と artifact を残し、目標未達でも原因分析できる |
| shutdown 確認 | 未定 | cancel/drain/release/close と shutdown 時間を記録する |

### 1.5 着手条件

- [x] `spec/complete/local_013/N3DSXL_ASYNC_STREAMING_ENGINE.md` の functional streaming が実装済み。
- [x] `tests/e2e` と `tests/performance` に marker が設定済み。
- [x] 人間承認前に実機 command を実行しない hook / 運用が有効である。
- [x] 実機 new 3DS XL capture board が接続され、product string または `product_string_status=unreadable` が確認できる。

### 1.6 Work Unit メタデータ

| 項目 | 内容 |
| ---- | ---- |
| 配置 | `spec/complete/local_014/N3DSXL_PERFORMANCE_AND_HARDWARE_GATES.md` |
| 対応 Step | Step 8: performance smoke test |
| 前提 Work Unit | `spec/complete/local_013/N3DSXL_ASYNC_STREAMING_ENGINE.md` |
| 次 Work Unit | MVP gate 結果により `spec/complete` 移動、または性能改善 / binding 再検討の新規 Work Unit。 |
| local task | marker gate、stats serializer、artifact path policy。 |
| hardware task | 60 秒 no-op consumer performance smoke。 |
| 選択条件 | functional streaming が実装済みで、MVP acceptance の性能 / shutdown / artifact が未検証のとき。 |
| 完了証拠 | local gate は unit / static / marker skip で確認済み。hardware gate は performance stats JSON、hardware log、shutdown result、未達時の原因仮説を承認後に報告する。 |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `tests/conftest.py` | 修正 | `requires_n3dsxl` と `performance` の env gate を定義する。 |
| `tests/e2e/test_n3dsxl_open_close.py` | 新規/修正 | open/claim/close E2E。 |
| `tests/e2e/test_n3dsxl_ftd3_pipe.py` | 新規/修正 | FTD3 command pipe E2E。 |
| `tests/e2e/test_n3dsxl_connect.py` | 新規/修正 | connect E2E。 |
| `tests/e2e/test_n3dsxl_raw_capture.py` | 新規/修正 | raw capture fixture E2E。 |
| `tests/e2e/test_n3dsxl_streaming.py` | 新規/修正 | functional streaming E2E。D3XX fallback backend で実機 gate を実行する。 |
| `tests/performance/test_n3dsxl_streaming_smoke.py` | 新規/修正 | 60 秒 performance smoke。D3XX fallback backend で実機 gate を実行する。 |
| `src/py3dscapture/hardware_gate.py` | 新規 | env gate と hardware command plan を提供する。 |
| `src/py3dscapture/artifacts.py` | 新規 | N3DSXL artifact path と JSON 上書き policy を提供する。 |
| `src/py3dscapture/streaming/stats.py` | 修正 | performance smoke 用の JSON stats を提供する。 |
| `src/py3dscapture/tools/stream_n3dsxl.py` | 新規/修正 | performance stats と JSON 出力を提供する。 |
| `tests/unit/test_hardware_gate.py` | 新規 | env gate と hardware command plan を検証する。 |
| `tests/unit/test_n3dsxl_artifacts.py` | 新規 | artifact path と上書き policy を検証する。 |
| `tests/unit/test_streaming_performance_stats.py` | 新規 | performance stats serializer を検証する。 |
| `tests/unit/test_stream_n3dsxl_cli.py` | 新規 | CLI `--stats-json` 出力を検証する。 |
| `tests/fixtures/n3dsxl/` | 未変更 | 承認済み raw fixture と metadata は実機承認後に保存する。 |
| `artifacts/n3dsxl/` | 未変更 | performance stats、logs、manual results は実機承認後の出力候補。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| hardware test を skip する | `PONKAN_RUN_N3DSXL` 未設定 | `requires_n3dsxl` test を skip する | CI 安全 |
| performance test を skip する | `PONKAN_RUN_PERFORMANCE` 未設定 | `performance` test を skip する | CI 安全 |
| command 承認を要求する | 実機 command 実行前 | `PONKAN_HARDWARE_APPROVED=1` が必要 | `.codex` hook と運用 |
| device identity を確認する | hardware gate 開始 | VID/PID/product string/product string status を報告する | readable unsupported product string は拒否 |
| open/close E2E を行う | approved hardware | 複数回 open/claim/close 成功 | cleanup |
| raw artifact を保存する | raw capture E2E | `.bin` と `.json` を保存する | 上書き不可が既定 |
| streaming E2E を行う | approved hardware | 10 秒程度の streaming で stats が出る | Step 7 gate |
| performance smoke を行う | approved hardware、performance env | 60 秒 streaming stats を保存する | Step 8 |
| shutdown を測る | stream stop | `shutdown <= 2 seconds` を目標に記録する | 初期目標 |
| 目標未達を扱う | fps < 50 など | stats と profile 結果を残し、binding / decoder / queue を分析する | 即失敗だけで終わらない |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | `PONKAN_RUN_N3DSXL` 未設定で requires_n3dsxl が skip される | safety | 3.1 | `tests/performance` collection skip と env helper unit |
| green | `PONKAN_RUN_PERFORMANCE` 未設定で performance が skip される | safety | 3.1 | `tests/performance` collection skip と env helper unit |
| green | hardware command plan に device identity と command scope が含まれる | safety | 3.1 | `tests/unit/test_hardware_gate.py` |
| green | raw capture artifact は `.bin` と `.json` の両方を持つ | regression | 3.1 | `tests/unit/test_raw_capture_metadata.py` |
| green | streaming stats に submitted/completed/decoded/delivered/dropped/errors が含まれる | regression | 3.1 | `tests/unit/test_streaming_performance_stats.py` |
| green | performance smoke は 60 秒 duration を使う | performance | 3.1 | `tests/performance/test_n3dsxl_streaming_smoke.py` |
| green | shutdown 時間を stats に含める | performance | 3.1 | `PerformanceStats` と smoke assertion |
| green | usb_errors が 0 であることを performance gate に含める | performance | 3.1 | smoke assertion |
| green | 60 秒 performance smoke を実機で実行し stats JSON を保存する | hardware-gated | 3.1 | D3XX backend で完了 |

### 3.3 設計方針

hardware gate は local gate と別物として扱う。Main Agent は実装後に local unit / type / lint を先に通し、実機が必要な時点で停止して次を説明する。

```text
- device identity: VID/PID/product string
- command scope: listing/open/ftd3/connect/raw/stream/performance のどれか
- safety reason: product string guard、marker、env gate、cleanup
- artifact: 保存する file / directory
- cleanup: cancel、drain、release、close
- command: 実行予定 command
```

Performance acceptance:

| 指標 | 初期目標 | 備考 |
| ---- | -------- | ---- |
| stream duration | 60 seconds | 2D mode |
| delivered fps | `>= 50` | no-op consumer |
| usb_errors | `0` | disconnect は別扱い |
| shutdown timeout | `<= 2 seconds` | cancel/drain/release/close |
| stats keys | submitted/completed/decoded/delivered/dropped/errors | JSON 保存 |
| output queue | bounded | `output_queue_size=2` |
| drop policy | `drop_oldest` | default |

### 3.4 Agentic SDD Task Graph

| 分類 | Task | Gate |
| ---- | ---- | ---- |
| Blocking local task | pytest marker gate と env skip を確認する | unit / pytest collection test |
| Blocking local task | StreamStats serializer と `--stats-json` を実装する | stats serializer test |
| Blocking local task | artifact path と上書き policy を実装する | artifact path test |
| Hardware task | 60 秒 no-op consumer performance smoke を実行する | human approval、performance marker |
| Review task | fps、drop、usb_errors、shutdown、binding の未達分析をまとめる | agentic-self-review |

performance gate は MVP acceptance だが、初回測定値は環境依存である。未達時は仕様失敗だけで閉じず、stats と原因仮説を残して次 Work Unit へ渡す。

## 4. 実装仕様

### 4.1 Pytest Markers

`pyproject.toml` の marker は維持する。

```toml
markers = [
    "requires_n3dsxl: requires a connected new 3DS XL capture board",
    "performance: performance smoke tests",
    "manual_visual: requires manual image inspection",
]
```

`tests/conftest.py` は次の gate を提供する。

```python
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_n3dsxl = os.environ.get("PONKAN_RUN_N3DSXL") == "1"
    run_performance = os.environ.get("PONKAN_RUN_PERFORMANCE") == "1"
    ...
```

### 4.2 Performance Stats

streaming CLI は `--stats-json` を受け取れるようにする。

```console
uv run python -m py3dscapture.tools.stream_n3dsxl --duration 60 --noop-consumer --stats --stats-json artifacts/n3dsxl/<timestamp>/stream_stats.json
```

stats JSON:

```json
{
  "model": "new_3ds_xl",
  "product_string": "N3DSXL",
  "mode_3d": false,
  "duration_seconds": 60,
  "raw_slots": 2,
  "output_queue_size": 2,
  "drop_policy": "drop_oldest",
  "submitted": 0,
  "completed": 0,
  "decoded": 0,
  "delivered": 0,
  "dropped_raw": 0,
  "dropped_decoded": 0,
  "usb_errors": 0,
  "decode_errors": 0,
  "shutdown_seconds": 0.0,
  "delivered_fps": 0.0
}
```

### 4.3 Artifact Policy

| Artifact | 保存先 | 上書き |
| -------- | ------ | ------ |
| raw fixture | `tests/fixtures/n3dsxl/raw_2d_001.bin` and `.json` | `--force` なしでは不可 |
| PNG candidate | `tests/fixtures/n3dsxl/candidate_*_top.png` など | `--force` なしでは不可 |
| performance stats | `artifacts/n3dsxl/<timestamp>/stream_stats.json` | timestamp directory |
| hardware log | `artifacts/n3dsxl/<timestamp>/hardware.log` | timestamp directory |
| manual result | `artifacts/n3dsxl/<timestamp>/manual_visual.json` | timestamp directory |

raw fixture を version 管理へ入れるかはサイズと内容を確認して別途判断する。初回は artifact として残し、必要なら dev-journal に扱いを記録する。

### 4.4 完了判定

| 判定 | 必須 evidence |
| ---- | ------------- |
| local complete | marker env gate、stats serializer、artifact policy の test が通る |
| performance pending | device identity、command scope、duration、artifact、cleanup を示して承認待ち |
| performance complete | 60 秒 stats JSON、delivered fps、usb_errors、drop count、shutdown seconds を報告 |
| MVP complete candidate | `local_009` から `local_014` の local/hardware gate 状態が揃い、未達事項が仕様または dev-journal に残る |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| conftest marker gate | env 未設定 | `requires_n3dsxl` item | skip |
| conftest marker gate | env 設定 | `requires_n3dsxl` item | run |
| stats serializer | StreamStats | sample stats | JSON keys が揃う |
| artifact path | timestamp path | run id | path が `artifacts/n3dsxl/` 配下 |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| hardware open/close | session cleanup | approval | 複数回成功 |
| functional streaming | 10 秒 stream | approval | stats 取得 |
| performance smoke | 60 秒 no-op stream | approval + performance env | fps/drop/error/shutdown 記録 |

### 検証コマンド

local:

```console
uv run pytest tests/unit
uv run ruff check .
uv run ty check --no-progress
```

hardware E2E:

```console
$env:PONKAN_RUN_N3DSXL = "1"
$env:PONKAN_HARDWARE_APPROVED = "1"
uv run pytest -m requires_n3dsxl tests/e2e
```

performance:

```console
$env:PONKAN_RUN_N3DSXL = "1"
$env:PONKAN_RUN_PERFORMANCE = "1"
$env:PONKAN_HARDWARE_APPROVED = "1"
uv run pytest -m "requires_n3dsxl and performance" tests/performance
```

manual performance CLI:

```console
$env:PONKAN_HARDWARE_APPROVED = "1"
uv run python -m py3dscapture.tools.stream_n3dsxl --duration 60 --noop-consumer --stats
```

## 6. 実装チェックリスト

- [x] `tests/conftest.py` の marker gate を確認・必要なら拡張する。
- [x] hardware E2E tests に `requires_n3dsxl` を付ける。
- [x] performance test に `requires_n3dsxl` と `performance` を付ける。
- [x] stream stats serializer と CLI stats JSON を実装する。
- [x] artifact 保存先と上書き policy を実装する。
- [x] functional streaming E2E を実機 D3XX backend で実行し gate 報告に残す。
- [x] performance smoke を実機 D3XX backend で実行し gate 報告に残す。
- [x] 未達指標は初回実機測定後に stats と原因仮説として残す方針を明記する。

## 7. 実装結果

### 7.1 Local Gate

| Gate | 結果 | Evidence |
| ---- | ---- | -------- |
| TDD red | pass | `uv run pytest tests/unit/test_hardware_gate.py tests/unit/test_streaming_performance_stats.py tests/unit/test_n3dsxl_artifacts.py` が未実装 import で失敗することを確認。 |
| Unit / marker skip | pass | `uv run pytest tests/unit -q`: 81 passed。`uv run pytest tests/e2e tests/performance -q`: 11 skipped。 |
| Performance collection | pass | `uv run pytest tests/performance`: `PONKAN_RUN_N3DSXL` 未設定により 1 skipped。 |
| Static | pass | `uv run ruff format --check .`、`uv run ruff check .`、`uv run ty check --no-progress`。 |
| Source audit | not applicable | 新規 cc3dsfs 由来 command / 構造体サイズは追加していない。 |
| Hardware | pass | 2026-06-08 に D3XX backend で functional E2E と 60 秒 performance smoke を実行した。 |

### 7.2 Hardware Approval Plan

| 項目 | 内容 |
| ---- | ---- |
| device identity | VID `0x0403`、PID `0x601e` / `0x601f` / `0x602a` / `0x602b` / `0x602c` / `0x602d` / `0x602f`、product string `N3DSXL` / `N3DSXL.2` を実行前に確認する。 |
| command scope | `performance`: 60 秒 2D no-op consumer streaming smoke。 |
| safety reason | `requires_n3dsxl`、`performance` marker、`PONKAN_RUN_*` env gate、`PONKAN_HARDWARE_APPROVED=1`、bounded queue、shutdown cleanup。 |
| artifact | `artifacts/n3dsxl/<timestamp>/stream_stats.json` と hardware log。 |
| cleanup | pending transfer cancel、drain、interface release、handle close。 |
| command | `PONKAN_RUN_N3DSXL=1`、`PONKAN_RUN_PERFORMANCE=1`、`PONKAN_HARDWARE_APPROVED=1` を同じ command 内に置いて `uv run pytest -m "requires_n3dsxl and performance" tests/performance` を実行する。 |

### 7.3 Hardware Gate Result

| Gate | 結果 | Evidence |
| ---- | ---- | -------- |
| device identity | pass | `0x0403:0x601e product=N3DSXL.2 serial=nxl530228`。 |
| functional streaming E2E | pass | `PONKAN_RUN_N3DSXL=1`、`PONKAN_HARDWARE_APPROVED=1` で `uv run pytest tests/e2e/test_n3dsxl_streaming.py -q`: 1 passed。 |
| hardware E2E suite | pass | 2026-06-08: `PONKAN_RUN_N3DSXL=1`、`PONKAN_HARDWARE_APPROVED=1` で `uv run pytest tests/e2e -q --basetemp artifacts\n3dsxl\20260608-185720\pytest-e2e`: 10 passed。raw `.bin` / `.json` artifacts を保存。 |
| performance smoke | pass | 2026-06-08: `PONKAN_RUN_N3DSXL=1`、`PONKAN_RUN_PERFORMANCE=1`、`PONKAN_HARDWARE_APPROVED=1` で `uv run pytest -m "requires_n3dsxl and performance" tests\performance -q --basetemp artifacts\n3dsxl\20260608-185720\pytest-performance`: 1 passed。 |
| performance stats | pass | `artifacts\n3dsxl\20260608-185720\pytest-performance\test_n3dsxl_streaming_60_secon0\n3dsxl\performance-smoke\stream_stats.json`: `backend_kind=d3xx`, `product_string=N3DSXL.2`, `delivered_fps=59.8`, `usb_errors=0`, `decode_errors=0`, `dropped_raw=1`, `shutdown_seconds=0.01651809993200004`。 |
| low latency default performance | pass | 2026-06-08: `local_021` で `raw_slots=2`, `poll_interval=0.004` を採用後、`artifacts\n3dsxl\20260608-233917\pytest-performance-rs2-poll4ms\test_n3dsxl_streaming_60_secon0\n3dsxl\performance-smoke\stream_stats.json`: `delivered_fps=59.81666666666667`, `usb_errors=0`, `decode_errors=0`, `dropped_raw=1`, `shutdown_seconds=0.0045770000433549285`。 |

### 7.4 Deferred

| 項目 | 理由 | 次の扱い |
| ---- | ---- | -------- |
| なし | 実機 functional / performance gate は D3XX backend で完了した。 | 新しい未達が出た場合は別 Work Unit で扱う。 |
