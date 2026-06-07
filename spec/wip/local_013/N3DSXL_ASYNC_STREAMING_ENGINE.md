# N3DSXL Async Streaming Engine 仕様書

更新日: 2026-06-07

## 1. 概要

### 1.1 目的

Step 7 として、libusb async transfer / callback 相当の非同期 read pipeline を実装し、USB acquisition、decode、consumer delivery を分離した continuous streaming API を提供する。

MVP 完了条件は single raw frame ではなく、この async streaming E2E までを含む。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| LibusbEventThread | libusb event handling を回し、async transfer callback が呼ばれる thread。 |
| RawFrameSlot | capture_size 分の事前確保 raw buffer と状態を持つ slot。 |
| AsyncRawTransferEngine | RawFrameSlot を submit / complete / resubmit / cancel する engine。 |
| RawFrameResult | callback で完了した raw slot、transferred length、status、sequence を表す結果。 |
| DecodeWorker | RawFrameResult から video region を切り出し、CaptureFrame を作る worker。 |
| Output Queue | consumer へ CaptureFrame を渡す bounded queue。 |
| Drop Policy | consumer が遅い場合に old/new/block のどれで扱うかを決める policy。 |
| StreamStats | submitted、completed、decoded、delivered、dropped、errors、cancelled を持つ統計。 |

### 1.3 背景・問題

MVP は high-performance streaming を含むため、同期 bulk read を繰り返すだけでは完了条件を満たさない。`cc3dsfs` の libusb acquisition path は複数 buffer と async transfer を使う。Python 版では内部実装をそのまま移植せず、callback を軽く保ち、decode と consumer delivery を別 layer に分ける。

callback 内で decode、Pillow 変換、blocking queue put、同期 libusb API 呼び出しを行わないことを安全制約にする。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| streaming | 実装なし | 複数 in-flight async transfer で連続 capture する |
| buffer allocation | 未定 | raw buffer を事前確保して再利用する |
| consumer 遅延 | 未定 | bounded queue と drop policy で固まらない |
| stats | 未定 | submitted/completed/decoded/delivered/dropped/errors を取得できる |
| shutdown | 未定 | cancel -> drain -> release -> close を完了する |

### 1.5 着手条件

- [ ] `spec/wip/local_012/N3DSXL_RAW_CAPTURE_FIXTURE_AND_DECODER.md` の 2D decoder と CaptureFrame が実装済み。
- [ ] `spec/wip/local_011/N3DSXL_FTD3_PIPE_AND_CONNECT.md` の 2D connect が実装済み。
- [ ] libusb binding が async transfer、callback、cancel、event handling を扱えることを確認済み。
- [ ] 実機 streaming E2E を実行する場合、人間承認がある。

### 1.6 Work Unit メタデータ

| 項目 | 内容 |
| ---- | ---- |
| 配置 | `spec/wip/local_013/N3DSXL_ASYNC_STREAMING_ENGINE.md` |
| 対応 Step | Step 7: async streaming engine |
| 前提 Work Unit | `spec/wip/local_011/N3DSXL_FTD3_PIPE_AND_CONNECT.md`、`spec/wip/local_012/N3DSXL_RAW_CAPTURE_FIXTURE_AND_DECODER.md` |
| 次 Work Unit | `spec/wip/local_014/N3DSXL_PERFORMANCE_AND_HARDWARE_GATES.md` |
| local task | buffer pool、drop policy、fake async backend、callback contract、sync/async iterator。 |
| sidecar task | libusb async acquisition と cancellation の source audit。 |
| hardware task | 10 秒 functional streaming E2E。 |
| 選択条件 | raw frame / decoder bring-up が完了し、continuous async streaming が未実装のとき。 |
| 完了証拠 | fake async tests が callback 非 blocking と shutdown order を証明し、実機 streaming gate の状態が報告されている。 |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `src/py3dscapture/transport/libusb_async.py` | 新規 | async transfer primitive と event thread を提供する。 |
| `src/py3dscapture/streaming/buffers.py` | 新規 | RawFrameSlot と buffer pool を定義する。 |
| `src/py3dscapture/streaming/engine.py` | 新規 | async raw transfer、decode worker、output queue を統合する。 |
| `src/py3dscapture/streaming/stats.py` | 新規 | StreamStats と snapshot を定義する。 |
| `src/py3dscapture/streaming/policies.py` | 新規 | DropPolicy と queue 操作を定義する。 |
| `src/py3dscapture/capture.py` | 修正 | `frames()` と `frames_async()` を public API として公開する。 |
| `src/py3dscapture/tools/stream_n3dsxl.py` | 新規 | streaming CLI と stats 表示を提供する。 |
| `tests/unit/test_streaming_buffers.py` | 新規 | buffer pool と slot lifecycle を検証する。 |
| `tests/unit/test_streaming_policies.py` | 新規 | drop policy を検証する。 |
| `tests/unit/test_streaming_engine_fake_async.py` | 新規 | fake async backend で submit/callback/shutdown を検証する。 |
| `tests/e2e/test_n3dsxl_streaming.py` | 新規 | 実機 10 秒程度の streaming E2E を検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| raw slot を事前確保する | `raw_slots=4`, `capture_size=555008` | 4 個の bytearray を作る | per-frame allocation を避ける |
| transfer を submit する | engine start | raw_slots 個の async transfer が in-flight になる | 実機 gate |
| callback を軽く保つ | transfer complete | status、actual length、slot index、sequence、completed_ns だけを記録し completion queue へ通知する | decode しない |
| callback が blocking しない | completion queue が詰まる | blocking put で止まらない | drop/error/cancel policy を明示 |
| decode worker へ渡す | RawFrameResult | video region を decoder へ渡し CaptureFrame を作る | raw slot lifetime 管理 |
| decoded frame を delivery する | Output Queue に空きあり | consumer が frame を受け取れる | `frames()` / `frames_async()` |
| consumer が遅い | Output Queue full | default は `drop_oldest` | recording は MVP 外 |
| stats を更新する | streaming 中 | submitted/completed/decoded/delivered/dropped/errors が増える | snapshot |
| stop する | context manager exit / Ctrl-C | pending transfer cancel、drain、worker stop、interface release、handle close | 順序を守る |
| async API を使う | asyncio 利用者 | `frames_async()` が async iterator を返す | libusb event loop を asyncio に直結しない |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | RawFrameSlot は capture_size 分の buffer を持つ | new behavior | 3.1 | unit |
| todo | BufferPool は raw_slots 個を事前確保する | new behavior | 3.1 | unit |
| todo | checkout 済み slot は二重 checkout できない | regression | 3.1 | unit |
| todo | `drop_oldest` は満杯 queue の最古 frame を捨てる | new behavior | 3.1 | unit |
| todo | `drop_newest` は新規 frame を捨てる | new behavior | 3.1 | unit |
| todo | `block` は callback thread では使われない | safety | 3.1 | design guard |
| todo | fake async backend で start 時に raw_slots 個 submit される | new behavior | 3.1 | unit |
| todo | fake callback は decode worker へ RawFrameResult を渡す | new behavior | 3.1 | unit |
| todo | stop は cancel -> drain -> release の順序を守る | regression | 3.1 | unit |
| todo | callback 内で decoder が呼ばれない | safety | 3.1 | fake spy |
| todo | `frames()` が CaptureFrame iterator として動く | new behavior | 3.1 | fake engine |
| todo | `frames_async()` が async iterator として動く | new behavior | 3.1 | fake engine |
| todo | 実機で 10 秒 streaming でき、stats が出る | hardware | 3.1 | `requires_n3dsxl` |

### 3.3 設計方針

初期構成:

```text
LibusbEventThread
  -> callback
AsyncRawTransferEngine
  -> RawFrameResult queue
DecodeWorker
  -> CaptureFrame output queue
Consumer API
  -> frames()
  -> frames_async()
```

MVP defaults:

| 設定 | 既定値 | 理由 |
| ---- | ------ | ---- |
| `raw_slots` | `4` または `6` | 複数 in-flight を確保する |
| `raw_slot_size` | `capture_size(False)` | 2D first |
| `output_queue_size` | `2` | 最新 frame 重視 |
| `drop_policy` | `drop_oldest` | real-time 表示用途 |
| `copy_policy` | `copy_decoded_frame_before_release_raw_slot` | raw slot 再利用による ndarray 破壊を避ける |

Source Audit:

| 項目 | 参照元候補 | 状態 |
| ---- | ---------- | ---- |
| async acquisition structure | `3dscapture_ftd3_libusb_acquisition.cpp` | audit required |
| in-flight buffer の考え方 | 同上 | audit required |
| cancel / shutdown sequence | 同上 | audit required |
| libusb async API | libusb async I/O API | primary doc 確認が必要 |

Hardware:

```text
- 実機 streaming command は human approval まで実行しない。
- performance ではなく functional streaming は 10 秒程度から始める。
- raw artifact は必要に応じて保存し、通常 streaming では全 frame を保存しない。
- stop 時間と usb_errors を必ず報告する。
```

### 3.4 Agentic SDD Task Graph

| 分類 | Task | Gate |
| ---- | ---- | ---- |
| Blocking local task | RawFrameSlot と BufferPool の lifecycle を TDD 実装する | buffer unit test |
| Blocking local task | drop policy と bounded output queue を TDD 実装する | policy unit test |
| Blocking local task | fake async backend で submit/callback/decode handoff を固定する | fake engine unit test |
| Blocking local task | `frames()` と `frames_async()` の iterator contract を実装する | fake frame delivery test |
| Sidecar task | libusb async API、callback thread、cancel/drain の source audit を行う | source audit note |
| Hardware task | 10 秒 streaming E2E と stats 表示 | human approval、`requires_n3dsxl` |

この仕様は 60 秒 performance smoke を扱わない。functional streaming が成立した後、性能測定と artifact policy は `local_014` に渡す。

## 4. 実装仕様

### 4.1 Types

```python
DropPolicy = Literal["drop_oldest", "drop_newest", "block"]
CopyPolicy = Literal["copy_decoded_frame_before_release_raw_slot", "zero_copy_experimental"]

@dataclass(slots=True)
class RawFrameSlot:
    index: int
    buffer: bytearray
    view: memoryview
    in_use: bool = False
    submitted_ns: int | None = None
    completed_ns: int | None = None
    transferred: int = 0
    sequence: int | None = None

@dataclass(slots=True)
class RawFrameResult:
    slot_index: int
    view: memoryview
    transferred: int
    status: int
    completed_ns: int
    sequence: int

@dataclass(slots=True)
class StreamStats:
    submitted: int = 0
    completed: int = 0
    decoded: int = 0
    delivered: int = 0
    dropped_raw: int = 0
    dropped_decoded: int = 0
    usb_errors: int = 0
    decode_errors: int = 0
    cancelled: int = 0
    last_error: str | None = None
```

### 4.2 Engine

```python
class StreamingEngine:
    def start(self) -> None: ...
    def stop(self, timeout: float | None = None) -> None: ...
    def frames(self) -> Iterator[CaptureFrame]: ...
    async def frames_async(self) -> AsyncIterator[CaptureFrame]: ...
    def stats(self) -> StreamStats: ...
```

`start()` は connect 済み N3DSXL device を前提にする。`stop()` は冪等で、例外時も interface release と handle close へ進む。

### 4.3 Callback Contract

callback 内で許可する処理:

```text
- monotonic timestamp の取得
- status / transferred / slot index / sequence の読み取り
- stats counter の軽量更新
- non-blocking completion notification
```

callback 内で禁止する処理:

```text
- ndarray decode
- Pillow 変換
- ファイル保存
- blocking queue put
- 同期 libusb API 呼び出し
- 長時間 lock を保持する処理
```

### 4.4 Drop Policy

```python
def put_frame_with_policy(
    queue: BoundedFrameQueue,
    frame: CaptureFrame,
    policy: DropPolicy,
    stats: StreamStats,
) -> None:
    ...
```

`block` は consumer API 側でのみ許容し、callback thread では使わない。MVP default は `drop_oldest`。

### 4.5 完了判定

| 判定 | 必須 evidence |
| ---- | ------------- |
| local complete | buffer、drop policy、fake async engine、iterator tests が通る |
| callback safety complete | callback 内で decode / Pillow / blocking put / sync libusb API を呼ばない test または review evidence がある |
| shutdown complete | cancel -> drain -> worker stop -> release -> close の順序を fake backend で確認する |
| hardware pending | streaming command scope、duration、stats artifact、cleanup を示して承認待ち |
| hardware complete | 10 秒 streaming E2E の delivered count、drop count、usb_errors、shutdown result を報告 |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| buffers | preallocation | raw_slots=4 | 4 slots |
| buffers | lifecycle | checkout/release | in_use 遷移 |
| policies | drop_oldest | full queue | oldest dropped |
| policies | drop_newest | full queue | new frame dropped |
| fake engine | submit count | raw_slots=4 | 4 submit |
| fake callback | no decode in callback | decoder spy | callback 中 call なし |
| shutdown | call order | fake backend | cancel -> drain -> release |
| async API | async iteration | fake frames | frames delivered |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| 10 秒 streaming | CaptureFrame delivery と stats | human approval | hang なし、stats 表示 |
| slow consumer | queue full | fake or hardware | drop policy 適用 |
| Ctrl-C / exit | cleanup | fake or hardware | pending transfer が残らない |

### 検証コマンド

```console
uv run pytest tests/unit/test_streaming_buffers.py tests/unit/test_streaming_policies.py tests/unit/test_streaming_engine_fake_async.py
uv run ruff check src/py3dscapture tests/unit/test_streaming_buffers.py tests/unit/test_streaming_policies.py tests/unit/test_streaming_engine_fake_async.py
uv run ty check --no-progress
```

実機 gate:

```console
$env:PONKAN_RUN_N3DSXL = "1"
$env:PONKAN_HARDWARE_APPROVED = "1"
uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_streaming.py
```

manual smoke:

```console
$env:PONKAN_HARDWARE_APPROVED = "1"
uv run python -m py3dscapture.tools.stream_n3dsxl --duration 10 --stats
```

## 6. 実装チェックリスト

- [ ] libusb async acquisition の source audit を記録する。
- [ ] buffer pool の unit test を書く。
- [ ] drop policy の unit test を書く。
- [ ] fake async backend で start/callback/stop の unit test を書く。
- [ ] `transport/libusb_async.py` を実装する。
- [ ] `streaming/*` を実装する。
- [ ] public `frames()` / `frames_async()` を実装する。
- [ ] `stream_n3dsxl` CLI を実装する。
- [ ] 実機 streaming E2E は人間承認まで未実行として報告する。
