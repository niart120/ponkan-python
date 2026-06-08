# D3XX Streaming Latency Measurement 仕様書

更新日: 2026-06-08

## 1. 概要

### 1.1 目的

D3XX streaming の fast path 実装可否を fps ではなく latency / jitter / queue 滞留の実測で判断できるよう、`StreamingEngine` に opt-in timing collection を追加する。

この Work Unit では D3XX fast path prototype は実装しない。現在の sequential D3XX worker がどこで詰まるかを測るための artifact schema と判断基準を先に固定する。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| Sequential D3XX worker | `D3xxAsyncBackend` が blocking `read_pipe()` を worker thread 上で順に実行し、既存 `StreamingEngine` callback 境界へ渡す現在の実装。 |
| Timing Collection | `StreamingEngine(collect_timing=True)` のときだけ per-transfer sample を保持し、summary を出す計測モード。 |
| Backend Queue Wait | transfer submission から backend worker が実 read を開始するまでの時間。 |
| Read Duration | backend worker の read 開始から completion callback までの時間。 |
| Completion Interval Jitter | backend completion 間隔のばらつき。60fps 付近なら平均 fps だけではなく p95 / p99 の伸びを見る。 |
| Completion Queue Wait | callback が completion queue に入れた後、processing loop が取り出すまでの時間。 |
| Callback-to-Resubmit | completion timestamp から同 slot の再 submit 直前までの時間。decode / queue wait / drop handling を含む。 |
| Fast Path | `FT_ReadPipeEx` / overlapped buffer などを Python から直接使う opt-in backend 候補。今回の実装対象外。 |

### 1.3 背景・問題

`local_016` で Windows D3XX fallback backend を実装し、60 秒 performance smoke は約 60fps を満たした。一方で、平均 fps は stream の余裕や jitter を示さない。D3XX fast path を入れる前に、現在の sequential worker が問題になっているのかを read latency、queue wait、completion interval、decode time、shutdown time で判定する必要がある。

原典 `cc3dsfs` は Windows D3XX path で `FT_ReadPipeEx` と複数 `OVERLAPPED` buffer を使う acquisition loop を持つ。FTDI D3XX Programmer's Guide も FT60X の性能設計として multiple asynchronous transfers と streaming mode を示している。ただし Python でこれを急いで再現すると、native buffer lifetime、overlapped structure、callback / drain の安全性が新しいリスクになる。

したがって、この Work Unit は fast path ではなく計測を先に入れる。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| 性能判断 | `delivered_fps` と counter 中心 | latency / jitter / queue 滞留の p50 / p95 / p99 / max で判断 |
| artifact schema | timing 情報なし | timing 有効時だけ `timing` section を追加 |
| 通常 API | 常に counter のみ | timing 無効時は既存 JSON schema を維持 |
| fast path 判断 | 事前に実装しがち | current worker の問題が測定で確認された場合だけ後続 Work Unit で設計 |
| 実機 gate | fps 合否に偏る | `usb_errors=0`、`decode_errors=0`、short/drop 理由、latency/jitter、shutdown を併せて見る |

### 1.5 着手条件

- [x] D3XX fallback backend と streaming smoke が既に動作している。
- [x] production decoder API cleanup が完了し、streaming default decoder が確定している。
- [x] D3XX fast path は今回の Work Unit の非対象として固定する。
- [x] 実機 command は人間承認なしに実行しない。

### 1.6 Work Unit メタデータ

| 項目 | 内容 |
| ---- | ---- |
| 配置 | `spec/complete/local_021/D3XX_STREAMING_LATENCY_MEASUREMENT.md` |
| 対応 Step | Step 7-8 follow-up: D3XX streaming latency / jitter measurement |
| 前提 Work Unit | `local_013`、`local_014`、`local_016`、`local_019` |
| local task | timing collector、artifact schema、D3XX worker timestamp、unit tests |
| hardware task | D3XX backend の 10 秒 timing smoke と 60 秒 performance smoke。明示承認後のみ実行 |
| 選択条件 | fast path 実装の前に current sequential worker の余裕と jitter を判断したいとき |
| 完了証拠 | unit tests、ruff、ty、spec、未実行 hardware gate の明示 |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/complete/local_021/D3XX_STREAMING_LATENCY_MEASUREMENT.md` | 新規 | D3XX streaming 計測仕様と fast path 判断基準を記録する。 |
| `spec/complete/local_008/WORK_UNIT_INDEX.md` | 修正 | follow-up Work Unit として `local_021` を索引に追加する。 |
| `src/py3dscapture/streaming/buffers.py` | 修正 | `RawFrameSlot` / `RawFrameResult` に backend read start timestamp を追加する。 |
| `src/py3dscapture/streaming/engine.py` | 修正 | opt-in timing collection と `timing_summary()` を追加する。 |
| `src/py3dscapture/streaming/stats.py` | 修正 | timing collector、summary、`PerformanceStats.timing` を追加する。 |
| `src/py3dscapture/transport/d3xx_streaming.py` | 修正 | worker 実 read 開始時刻を slot に記録する。 |
| `src/py3dscapture/tools/stream_n3dsxl.py` | 修正 | `--collect-timing` と performance artifact の `timing` section を追加する。 |
| `tests/unit/test_streaming_engine_fake_async.py` | 修正 | timing summary、short transfer、timing disabled の unit test を追加する。 |
| `tests/unit/test_d3xx_streaming_backend.py` | 修正 | D3XX worker が `backend_started_ns` を記録することを確認する。 |
| `tests/unit/test_streaming_performance_stats.py` | 修正 | timing section の JSON 出力を確認する。 |
| `tests/unit/test_stream_n3dsxl_cli.py` | 修正 | timing 無効時の既存 schema 維持と `--collect-timing` を確認する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| timing 無効で smoke を実行する | 既定の `StreamingEngine` | 既存 counter と `delivered_fps` の JSON schema が維持され、`timing` key は出ない | 後方互換 |
| timing 有効で smoke を実行する | `collect_timing=True` または CLI `--collect-timing` | `timing` section に metric summary が出る | sample は memory 上に保持 |
| backend wait を測る | slot submit 後、worker read 開始前に待ちがある | `backend_queue_wait_ms` に記録される | D3XX worker は read 直前に timestamp |
| read latency を測る | worker read start から callback completion | `read_duration_ms` と `submit_to_complete_ms` に記録される | backend start がない backend では available な metric だけ出す |
| completion interval を測る | 複数 completion が発生 | `completion_interval_ms` が 2 件目以降に記録される | jitter 判定用 |
| queue 滞留を測る | completion queue から processing loop が取り出す | `completion_queue_wait_ms` に記録される | callback 内 decode はしない |
| decode 時間を測る | successful raw completion を decode する | `decode_ms` に記録される | short transfer / usb error では decode しない |
| resubmit までを測る | result 処理後に同 slot を再 submit する | `callback_to_resubmit_ms` に記録される | queue wait と decode を含む |
| short transfer を処理する | `transferred < video_size` | decode せず `dropped_raw` を増やし、timing collector は壊れない | 既存 guard 維持 |
| usb error を処理する | `status != 0` | decode せず `usb_errors` を増やし、timing collector は壊れない | 既存 guard 維持 |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | fake backend completion で timing summary が計算される | behavior | 3.1 | deterministic clock |
| green | short transfer は decode せず timing と drop counter が壊れない | regression | 3.1 | `decode_ms` sample なし |
| green | timing 無効時は summary がなく、既存 stats JSON に `timing` が出ない | compatibility | 3.1 | default off |
| green | `D3xxAsyncBackend` が worker 実 read 開始時刻を slot に記録する | behavior | 3.1 | `backend_started_ns` |
| green | CLI `--collect-timing` で performance artifact に `timing` が出る | tool behavior | 3.1 | fake engine |
| green | 実機 D3XX backend で 10 秒 timing smoke を実行する | hardware | 3.1 | `artifacts\n3dsxl\20260608-230954\timing-smoke\stream_stats.json` |
| green | 実機 D3XX backend で 60 秒 performance smoke を実行する | hardware | 3.1 | `artifacts\n3dsxl\20260608-230954\pytest-performance-timing\...stream_stats.json` |

### 3.3 設計方針

Timing collection は opt-in に閉じる。通常 API の runtime path は collector object も sample list も作らず、`PerformanceStats.to_dict()` も既存 key のままにする。

summary は次の形式で metric ごとに出す。

```json
{
  "timing": {
    "read_duration_ms": {
      "count": 3600,
      "min": 14.1,
      "p50": 16.6,
      "p95": 17.8,
      "p99": 22.4,
      "max": 31.0,
      "mean": 16.9
    }
  }
}
```

60 秒程度の smoke では全 sample を memory 上に保持してよい。長時間 production telemetry や rolling window はこの Work Unit の非対象にする。

Source Audit:

| 項目 | 参照元 | 状態 |
| ---- | ------ | ---- |
| D3XX async acquisition | `https://github.com/Lorenzooone/cc3dsfs/blob/main/source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_driver_acquisition.cpp` | 原典は Windows で `FT_ReadPipeEx`、複数 `OVERLAPPED` buffer、concurrent buffer を使う。今回は再実装しない。 |
| D3XX performance guidance | `https://ftdichip.com/wp-content/uploads/2020/08/AN_379-D3xx-Programmers-Guide.pdf` | FTDI guide は FT60X の性能設計として multiple asynchronous transfers と streaming mode を示す。 |
| Python native buffer lifetime | `https://docs.python.org/3/library/ctypes.html` | `ctypes` object は参照保持や shared buffer の lifetime を明示的に扱う必要がある。fast path 設計時の安全前提として記録する。 |

Fast path 判断:

| 観測 | 判断 |
| ---- | ---- |
| `backend_queue_wait_ms` p95 / p99 が小さく、`completion_interval_ms` も安定 | current sequential worker を維持し、fast path は不要。 |
| `backend_queue_wait_ms` または `callback_to_resubmit_ms` p95 / p99 が伸び、completion interval jitter と相関 | processing loop / queue / resubmit path の改善を優先。 |
| `read_duration_ms` p95 / p99 が大きく伸び、backend queue は小さい | D3XX read / device / driver 側の jitter として扱い、fast path で改善するかは追加検証。 |
| completion queue wait が伸び、decode が重い | decode worker / consumer / queue policy の設計を優先。 |
| usb error / decode error が非ゼロ | latency 判断より先に correctness / safety bug として扱う。 |
| current worker の queue wait / jitter が問題と確認 | 次 Work Unit で opt-in D3XX fast path backend を仕様化する。 |

## 4. 実装仕様

### 4.1 Public / Internal API

```python
engine = StreamingEngine(
    D3xxAsyncBackend(handle),
    raw_slots=4,
    output_queue_size=2,
    drop_policy="drop_oldest",
    collect_timing=True,
)

stats = run_streaming_smoke(...)
stats.to_dict()["timing"]["read_duration_ms"]["p95"]
```

追加 API:

| API | 内容 |
| --- | ---- |
| `StreamingEngine(..., collect_timing=False)` | timing collection を opt-in で有効化する。 |
| `StreamingEngine.timing_summary()` | timing 有効時は summary dict、無効時は `None` を返す。 |
| `PerformanceStats.from_stream_stats(..., timing=...)` | timing summary を artifact に含める。 |
| `PerformanceStats.to_dict()` | timing が `None` の場合は `timing` key を省略する。 |
| `stream_n3dsxl --collect-timing` | CLI smoke で timing collection を有効化する。 |

### 4.2 Timestamp Flow

| Timestamp | 記録位置 | 用途 |
| --------- | -------- | ---- |
| `submitted_ns` | `StreamingEngine._submit_slot()` | submit-to-complete、backend queue wait |
| `backend_started_ns` | `D3xxAsyncBackend._read_into_slot()` | backend queue wait、read duration |
| `completed_ns` | backend callback | read duration、completion interval、queue wait |
| processing start | `StreamingEngine._process_result()` | completion queue wait |
| decode start/end | `StreamingEngine._process_result()` | decode time |
| resubmit start | `StreamingEngine._process_result()` finally | callback-to-resubmit |

`RawFrameResult` は `submitted_ns` と `backend_started_ns` を completion queue へ運ぶ。これにより slot release 後でも processing loop が計測できる。

### 4.3 Non-goals

```text
- FT_ReadPipeEx / OVERLAPPED を Python から直接呼ぶ fast path backend
- ctypes による direct DLL binding
- ring buffer / zero-copy decode pipeline の再設計
- production telemetry / rolling aggregation
- fps 合格基準の撤廃
- 実機 command の承認なし実行
```

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| `StreamingEngine` timing | fake backend + deterministic timestamps | 1 frame completion | metric summary が count/min/p50/p95/p99/max/mean を持つ |
| short transfer | `transferred < video_size` | fake completion | decode せず `dropped_raw`、`decode_ms` なし |
| timing disabled | default engine | fake completion | `timing_summary() is None` |
| `D3xxAsyncBackend` | worker read start | fake handle | `slot.backend_started_ns is not None` |
| `PerformanceStats` | timing section | synthetic summary | `to_dict()["timing"]` が出る |
| CLI | `--collect-timing` | fake engine | stats JSON に `timing` が出る |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| timing smoke | D3XX backend 10 秒 | N3DSXL 実機、承認済み command | errors 0、timing summary artifact |
| performance smoke | D3XX backend 60 秒 | N3DSXL 実機、承認済み command | fps だけでなく p95 / p99 latency と jitter を確認 |

### 検証コマンド

```console
uv run pytest tests/unit/test_streaming_engine_fake_async.py tests/unit/test_d3xx_streaming_backend.py tests/unit/test_streaming_performance_stats.py tests/unit/test_stream_n3dsxl_cli.py -q
uv run ruff check src tests
uv run ty check --no-progress
```

Hardware-gated command scope:

```console
$env:PONKAN_RUN_N3DSXL = "1"
$env:PONKAN_HARDWARE_APPROVED = "1"
uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_streaming.py -q

$env:PONKAN_RUN_PERFORMANCE = "1"
uv run pytest -m "requires_n3dsxl and performance" tests/performance -q
```

実機 gate の合否は fps 単独では判定しない。`usb_errors=0`、`decode_errors=0`、short/drop が説明可能、p95 / p99 latency と completion interval jitter が異常に伸びないこと、shutdown が bounded であることを見る。

## 6. 実装チェックリスト

- [x] D3XX streaming latency 計測仕様を作成する。
- [x] `RawFrameSlot` / `RawFrameResult` に backend read start timestamp を追加する。
- [x] `StreamingEngine` に opt-in timing collection を追加する。
- [x] summary を `count/min/p50/p95/p99/max/mean` で出す。
- [x] `run_streaming_smoke` / performance artifact に timing section を追加する。
- [x] timing 無効時の JSON 後方互換を維持する。
- [x] `D3xxAsyncBackend` が worker 実 read 開始時刻を記録する。
- [x] unit tests を追加する。
- [x] 指定 pytest / ruff / ty を実行する。
- [x] diff whitespace check を実行する。
- [x] self-review を完了する。
- [x] 実機 streaming smoke を実行する。
- [x] 実機 timing smoke を実行する。
- [x] 実機 performance smoke を実行する。

## 7. Gate Results

| Gate | 結果 | Evidence |
| ---- | ---- | -------- |
| Targeted unit | pass | `uv run pytest tests/unit/test_streaming_engine_fake_async.py tests/unit/test_d3xx_streaming_backend.py tests/unit/test_streaming_performance_stats.py tests/unit/test_stream_n3dsxl_cli.py -q`: 19 passed |
| Ruff | pass | `uv run ruff check src tests`: All checks passed |
| Type | pass | `uv run ty check --no-progress`: All checks passed |
| Diff | pass | `git diff --check` |
| Hardware streaming smoke | pass | `$env:PONKAN_RUN_N3DSXL='1'; $env:PONKAN_HARDWARE_APPROVED='1'; $env:PONKAN_N3DSXL_DRIVER_SERVICE='FTDIBUS3'; uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_streaming.py -q --basetemp artifacts\n3dsxl\20260608-230954\pytest-e2e-timing`: 1 passed in 2.86s |
| Hardware timing smoke | pass | `collect_timing=True` の D3XX 10 秒 smoke。`artifacts\n3dsxl\20260608-230954\timing-smoke\stream_stats.json`: `delivered_fps=59.7`, `usb_errors=0`, `decode_errors=0`, `dropped_raw=1` |
| Hardware performance smoke | pass | `$env:PONKAN_RUN_N3DSXL='1'; $env:PONKAN_RUN_PERFORMANCE='1'; $env:PONKAN_HARDWARE_APPROVED='1'; $env:PONKAN_N3DSXL_DRIVER_SERVICE='FTDIBUS3'; uv run pytest -m "requires_n3dsxl and performance" tests/performance/test_n3dsxl_streaming_smoke.py -q --basetemp artifacts\n3dsxl\20260608-230954\pytest-performance-timing`: 1 passed in 60.83s |

## 8. Timing Evaluation

3DS 実機の refresh rate を 59.834Hz とすると、1 frame period は `1000 / 59.834 = 16.7129ms` である。

10 秒 timing smoke の D3XX artifact は次の通り。

| Metric | p50 | p95 | p99 | max | frame 換算 / 評価 |
| ------ | --- | --- | --- | --- | ----------------- |
| `completion_interval_ms` | 16.7153ms | 16.8542ms | 16.9122ms | 17.0802ms | p50 は refresh period +0.0024ms、p99 は +0.1993ms。1 frame 周期へよく同期している。 |
| `read_duration_ms` | 16.6520ms | 16.7720ms | 16.8405ms | 16.9680ms | p50 は 0.996 frames、p99 は 1.008 frames。read はほぼ 1 frame 分で安定している。 |
| `backend_queue_wait_ms` | 44.3788ms | 49.0211ms | 49.3043ms | 49.5666ms | p50 は 2.66 frames、p99 は 2.95 frames。`raw_slots=4` かつ sequential worker の先行 submit queue を反映している。 |
| `completion_queue_wait_ms` | 4.9303ms | 9.5477ms | 10.1124ms | 10.2773ms | poll interval 10ms の影響を受ける。callback path そのものの USB jitter ではない。 |
| `decode_ms` | 0.6909ms | 1.0906ms | 1.1491ms | 1.2381ms | p99 でも 0.069 frames。decode は latency 支配要因ではない。 |
| `callback_to_resubmit_ms` | 5.7683ms | 10.3459ms | 10.8824ms | 11.0163ms | completion queue wait と decode を含む。p99 は 0.65 frames。 |
| `submit_to_complete_ms` | 61.1003ms | 65.6884ms | 66.0014ms | 66.1813ms | p50 は 3.66 frames、p99 は 3.95 frames。slot submit から completion までの in-flight pipeline depth を示す。 |

推定できる遅延は計測起点ごとに分ける。

| 起点 | 推定値 | 解釈 |
| ---- | ------ | ---- |
| USB completion から decoded frame enqueue まで | p50 約 `completion_queue_wait + decode = 5.62ms`、p99 約 `11.26ms` | Python processing / polling による host-side 追加遅延。poll interval 10ms が主因で、decode は小さい。 |
| slot submit から decoded frame enqueue まで | p50 約 `submit_to_complete + completion_queue_wait + decode = 66.72ms`、p99 約 `77.26ms` | `raw_slots=4` sequential worker の queue depth を含む host pipeline latency。約 4.0 frames p50、4.6 frames p99。 |
| 実画面変化から frame delivery まで | この artifact だけでは絶対値は確定不能 | USB payload に外部視覚 timestamp がないため、panel scanout / capture board 内部 buffering は別途 optical / timestamp fixture が必要。 |

今回の artifact では、completion interval と read duration は 59.834Hz に対して妥当で、短時間の jitter 異常は見えない。改善余地として見えているのは D3XX read 自体ではなく、`raw_slots=4` sequential worker の先行 queue depth と、10ms poll loop による completion queue wait である。fast path を検討する前に、低 latency mode として raw slot 数、poll interval、processing loop wakeup を切り分ける価値がある。

## 9. Completion Notes

今回の完了条件は「fast path を入れる」ことではなく「fast path が必要かを判断する計測を入れる」こととする。実機 timing smoke の結果、read duration と completion interval は 59.834Hz の frame period に整合し、decode も p99 約 1.15ms と小さい。一方で submit 起点の latency は raw slot queue depth を含み約 4 frame 規模になるため、次の低 latency 検討では fast path 直行ではなく raw slots / poll interval / wakeup path の切り分けを優先する。
