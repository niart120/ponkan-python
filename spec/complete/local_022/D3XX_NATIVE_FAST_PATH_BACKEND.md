# D3XX Native Fast Path Backend 仕様書

更新日: 2026-06-08

## 1. 概要

### 1.1 目的

D3XX streaming の USB read 経路を native D3XX API の想定 usage に近づけ、Python 側の余分な queue / copy / wakeup を減らす opt-in backend を設計する。

この Work Unit は設計を固定する段階であり、`D3xxAsyncBackend` の置き換えや fast path 実装は行わない。`local_021` の結果で採用した `raw_slots=2`, `poll_interval=0.004` の低遅延 default は維持する。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| Sequential D3XX backend | 現行 `D3xxAsyncBackend`。`ThreadPoolExecutor` 上で blocking `D3xxHandle.read_pipe()` を順に実行し、完了後に `RawFrameSlot.buffer` へコピーして callback する backend。 |
| Native fast path backend | D3XX DLL の native handle と preallocated buffer / overlapped read を使い、Python 側の read queue、buffer allocation、copy、poll wakeup を減らす opt-in backend 候補。 |
| Direct DLL path | PyD3XX wrapper を経由せず、`ctypes` で `FTD3XX.DLL` function を呼ぶ経路。現行 `D3xxHandle` は一部 read/write で private `_DLL` と `_Handle` を利用している。 |
| Overlapped read | `FT_ReadPipeEx` に overlapped state を渡し、複数 read を in-flight にしたまま completion を待つ Windows D3XX path。 |
| Native buffer slot | D3XX read の書き込み先として lifetime を backend が明示管理する native buffer。最初は `ctypes.create_string_buffer()` を想定し、`RawFrameSlot.buffer` への direct write は安全性確認後に限定する。 |
| Completion pump | native completion を待ち、`StreamingEngine` の callback 境界へ完了だけを通知する専用 thread。callback 内で decode や blocking queue 操作をしない。 |
| Buffer lifetime owner | native buffer、overlapped state、event handle、Python slot 参照を completion / cancel / drain 完了まで保持する object。 |
| Opt-in backend | default にはせず、明示された CLI / config / test だけで使う backend。測定時に silent fallback しない。 |

### 1.3 背景・問題

`local_021` で D3XX streaming timing を追加し、`raw_slots=2`, `poll_interval=0.004` を低遅延 default として採用した。60 秒実機 timing smoke では `delivered_fps=59.8`、`usb_errors=0`、`decode_errors=0`、`completion_interval_ms.p99=16.8987ms`、`submit_to_complete_ms.p99=32.8708ms` であり、3DS 実機の 59.834Hz に対して安定している。

したがって fast path は現時点の fps 未達対策ではない。今後 GUI、recording、長時間運用、または host absolute latency をさらに詰める段階で、Python worker queue、per-read native buffer allocation、`bytes` 化、`RawFrameSlot.buffer` へのコピー、poll wakeup を減らすための別 backend として扱う。

現行 D3XX path は次の copy / wakeup を持つ。

```text
StreamingEngine
  -> D3xxAsyncBackend.submit_read()
  -> ThreadPoolExecutor queue
  -> worker thread
  -> D3xxHandle.read_pipe()
  -> FT_ReadPipeEx direct DLL path or PyD3XX wrapper
  -> native buffer / PyD3XX buffer
  -> bytes(...)
  -> RawFrameSlot.buffer[:transferred] = payload
  -> completion callback
  -> completion queue
  -> engine poll loop
```

Native fast path は次の方向へ寄せる。

```text
StreamingEngine checked-out raw slots
  -> Native buffer slot owner
  -> FT_ReadPipeEx(..., overlapped)
  -> completion pump waits native completion
  -> completion callback only carries status / transferred / timestamps
```

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| Backend queue | Python executor queue に read job を積む | native pending read を slot 数だけ維持し、Python job queue を減らす |
| Read buffer allocation | read ごとに `ctypes.create_string_buffer()` または wrapper buffer が作られる | backend start 時に native buffer slot を preallocate する |
| Copy | native buffer から `bytes`、さらに `RawFrameSlot.buffer` へコピー | Phase 1 は copy 1 回以下、Phase 2 で direct slot write を検証 |
| Wakeup | worker completion と engine poll loop | native completion pump から completion queue へ最小通知 |
| Latency 判断 | fps と sequential timing | `local_021` timing と同じ schema で sequential baseline と比較 |
| Safety | simple blocking read で安定 | buffer lifetime、cancel / drain、native handle ownership を unit test で固定してから実機へ進む |

### 1.5 着手条件

- [x] `local_021` の D3XX timing collection が完了している。
- [x] `raw_slots=2`, `poll_interval=0.004` の低遅延 default が実機 60 秒 smoke で安定している。
- [x] D3XX fallback backend が Windows 実機で動作している。
- [x] fast path を default にしない方針が確定している。
- [x] Direct DLL の handle / function surface は明示的な native binding として分離する。初期 adapter は PyD3XX 由来 DLL / handle を使ってよいが、fast path backend 本体は PyD3XX private internals を直接参照しない。
- [x] Overlapped structure と cancellation API の calling convention を FTDI D3XX Programmer's Guide v1.7、local PyD3XX 1.1.4 wrapper、loaded `FTD3XX.dll` export で再確認した。現環境に installed `ftd3xx.h` はないため、SDK header 入手時は差分確認だけを追加 gate にする。

### 1.6 Work Unit メタデータ

| 項目 | 内容 |
| ---- | ---- |
| 配置 | `spec/complete/local_022/D3XX_NATIVE_FAST_PATH_BACKEND.md` |
| 対応 Step | Step 7-8 follow-up: opt-in D3XX native fast path backend implementation |
| 前提 Work Unit | `local_013`、`local_016`、`local_021` |
| local task | native API wrapper、native fast path backend、fake native API unit、source audit、safety gate |
| hardware task | 10 秒 timing smoke、60 秒 performance smoke、sequential baseline 比較。承認後のみ実行 |
| 選択条件 | `local_021` の low latency default よりさらに copy / wakeup / host latency を減らす必要が出たとき |
| 完了証拠 | この仕様、Work Unit index、unit/static gate、実機 native timing / performance artifact |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/complete/local_022/D3XX_NATIVE_FAST_PATH_BACKEND.md` | 新規 | D3XX native fast path backend の設計、実装、非対象、test list、hardware gate を定義する。 |
| `spec/complete/local_008/WORK_UNIT_INDEX.md` | 修正 | follow-up Work Unit として `local_022` の完了状態と実機 gate 結果を反映する。 |
| `src/py3dscapture/transport/d3xx_backend.py` | 修正 | `D3xxNativeApi` adapter 用に PyD3XX 由来 DLL / native handle provider surface を追加する。 |
| `src/py3dscapture/transport/d3xx_native.py` | 新規 | D3XX DLL function surface、native handle、overlapped helper。 |
| `src/py3dscapture/transport/d3xx_native_streaming.py` | 新規 | opt-in native fast path backend。 |
| `src/py3dscapture/streaming/stats.py` | 修正 | performance artifact の `backend_kind=d3xx-native` を許容する。 |
| `src/py3dscapture/tools/stream_n3dsxl.py` | 修正 | streaming smoke helper が `d3xx-native` backend kind を記録できるようにする。 |
| `tests/unit/test_d3xx_native_api.py` | 新規 | native function signature、DLL surface、overlapped layout test。 |
| `tests/unit/test_d3xx_native_streaming_backend.py` | 新規 | fake native API による submit / completion / cancel / lifetime test。 |
| `tests/unit/test_streaming_performance_stats.py` | 修正 | `backend_kind=d3xx-native` の artifact schema regression test。 |
| `tests/e2e/test_n3dsxl_d3xx_native_streaming.py` | 新規 | native backend 10 秒 timing smoke。 |
| `tests/performance/test_n3dsxl_d3xx_native_streaming_smoke.py` | 新規 | native backend 60 秒 performance smoke。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| default backend を選ぶ | backend 指定なし | 現行 `D3xxAsyncBackend` を使う | fast path は default にしない |
| native backend を明示する | CLI / config / test で native backend を指定 | native DLL surface が利用可能な場合だけ起動する | 利用不可なら明示的な config error |
| native binding surface を作る | fast path が `D3xxHandle` を受け取る | `D3xxNativeApi` が DLL function surface と native handle provider を所有する | 初期 adapter は PyD3XX 由来 DLL / handle を許容する |
| native DLL surface がない | `D3xxNativeApi` が必要 function / handle を提供できない | silent fallback せず、native backend unavailable として失敗する | 測定結果の混同防止 |
| submit する | checked-out `RawFrameSlot` と read length | native buffer slot と overlapped state を確保済み owner に関連付け、read を pending にする | read ごとの allocation を避ける |
| completion を受ける | native read が成功 | `transferred`、`status=0`、timestamps を callback に渡す | callback 内で decode しない |
| short transfer を受ける | `transferred < video_size` | engine 側の既存 short transfer guard で decode せず drop counter を増やす | native backend は改変しない |
| native error を受ける | `FT_ReadPipeEx` / completion status が非 OK | `status` を callback に渡し、engine 側で `usb_errors` を増やす | error code は artifact に追加候補 |
| cancel する | shutdown / test cancel | 新規 submit を止め、pending overlapped を cancel / abort / drain し、completion pump を停止する | handle close より前に drain |
| release する | cancel / drain 後 | native buffer、overlapped state、event handle を release し、owner 参照を切る | pending 中には release しない |
| timing を集計する | `collect_timing=True` | `local_021` と同じ metrics を出す | sequential baseline と同じ評価軸 |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | native backend 指定時に DLL surface がなければ config error になる | behavior | 3.1 | `tests/unit/test_d3xx_native_api.py` |
| green | `NativeOverlapped` の size / offset が 64-bit Windows `OVERLAPPED` ABI と一致する | source-audit | 3.4 | expected size 32、`hEvent` offset 24 |
| green | `D3xxNativeApi` が `FT_ReadPipeEx` / `FT_GetOverlappedResult` / `FT_AbortPipe` の `argtypes` / `restype` を固定する | safety | 4.1.1 | ctypes の暗黙変換に依存しない |
| green | preallocated native buffer owner が completion まで buffer と overlapped state を保持する | safety | 3.1 | fake native API が owner lifetime を検査 |
| green | submit は read ごとの native buffer allocation を行わない | performance contract | 1.4 | fake allocator count |
| green | `FT_IO_PENDING` は pending、`FT_IO_INCOMPLETE` は未完了 poll として扱う | behavior | 4.1.1 | `FT_OK` 以外を即 error にしない |
| green | completion pump は callback へ `transferred` / `status` / timestamps だけを渡す | behavior | 3.1 | decode は engine 側 |
| green | short transfer は既存 engine で decode されず drop counter になる | regression | 3.1 | existing engine regression |
| green | native error は decode されず `usb_errors` になる | regression | 3.1 | fake status |
| green | cancel 後の新規 submit は拒否される | shutdown | 3.1 | race guard |
| green | release は pending overlapped の drain 前に native resources を解放しない | safety | 3.1 | fake call order |
| green | timing summary が sequential backend と同じ keys を持つ | compatibility | 3.1 | `local_021` schema |
| green | 実機 D3XX native backend 10 秒 timing smoke を実行する | hardware | 5 | `artifacts\n3dsxl\20260609-015237\3dsxl\native-timing-smoke-readable\stream_stats.json` |
| green | 実機 D3XX native backend 60 秒 performance smoke を実行する | hardware | 5 | `artifacts\n3dsxl\20260609-015307\3dsxl\native-performance-smoke-readable\stream_stats.json` |

### 3.3 設計方針

Native fast path は二段階で実装する。

| Phase | 内容 | 採用条件 |
| ----- | ---- | -------- |
| Phase 0 | `D3xxNativeApi` wrapper と fake native API test を作る。native function signature、overlapped lifecycle、cancel / drain order を固定する。 | 実機なしで lifecycle を検証できること |
| Phase 1 | `ctypes.create_string_buffer()` で native buffer slot を preallocate し、completion 後に `RawFrameSlot.buffer` へ最大 1 回コピーする。 | sequential baseline と同等以上に安定し、copy / allocation が減ること |
| Phase 2 | `RawFrameSlot.buffer` への direct write を検証する。`ctypes.from_buffer` などで Python buffer の lifetime と resize 禁止を owner が保証する。 | Phase 1 が安定し、direct write の lifetime test と実機 smoke が通ること |

Phase 1 では true zero-copy を急がない。最初の目的は native overlapped lifecycle と Python queue / allocation 削減の安全な導入である。Phase 2 は buffer lifetime の証拠が揃うまで実装しない。

Phase 0 / Phase 1 の途中で作る prototype、調査用 shim、重複 helper は永続 API としない。次 Phase へ進む時点で採用済みの native binding boundary へ統合するか削除し、最終実装後に残すのは production path、fake native API test、source audit 記録だけにする。中間実装との互換性は維持しない。

### 3.4 Source Audit

| 項目 | 参照元 | 状態 |
| ---- | ------ | ---- |
| cc3dsfs D3XX acquisition | `https://github.com/Lorenzooone/cc3dsfs/blob/main/source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_driver_acquisition.cpp` | 原典は Windows path で `FT_ReadPipeEx` と overlapped buffer を使う acquisition loop を持つ。実装 Work Unit で exact call order を再確認する。 |
| D3XX API surface | `https://ftdichip.com/wp-content/uploads/2020/08/AN_379-D3xx-Programmers-Guide.pdf` | v1.7 を確認。`FT_ReadPipeEx` は `FT_HANDLE, UCHAR, PUCHAR, ULONG, PULONG, LPOVERLAPPED`。`pOverlapped != NULL` では `FT_IO_PENDING` を許容し、完了は `FT_GetOverlappedResult` で取得する。失敗時は `FT_AbortPipe` で pipe を clean にする。 |
| D3XX overlapped lifecycle | `https://ftdichip.com/wp-content/uploads/2020/08/AN_379-D3xx-Programmers-Guide.pdf` | `FT_InitializeOverlapped` で初期化し、pending operation 完了または cancel / drain 後に `FT_ReleaseOverlapped` で release する。Guide の `FT_ReadPipeEx` sample に出る `FT_InitializeOverlappedEx` は function list / DLL export / PyD3XX wrapper にないため採用しない。 |
| local D3XX wrapper / DLL | `uv.lock`、`.venv/Lib/site-packages/PyD3XX/PyD3XX.py`、`.venv/Lib/site-packages/PyD3XX/FTD3XX.dll` | PyD3XX 1.1.4 は `ctypes.windll.LoadLibrary` で 64-bit `FTD3XX.dll` を load し、`FT_InitializeOverlapped` / `FT_GetOverlappedResult` / `FT_ReleaseOverlapped` / `FT_ReadPipeEx` / `FT_AbortPipe` export を持つ。installed `ftd3xx.h` は現環境では見つからなかった。 |
| Python native buffer | `https://docs.python.org/3/library/ctypes.html` | `ctypes.create_string_buffer()` と `from_buffer` 系の lifetime を Python object owner で保持する必要がある。 |
| 現行 direct DLL helper | `src/py3dscapture/transport/d3xx_backend.py` | `_direct_read_pipe_ex()` は `ctypes.create_string_buffer(length)` を read ごとに作り、`bytes(buffer.raw[:transferred])` を返す。 |
| 現行 sequential worker | `src/py3dscapture/transport/d3xx_streaming.py` | `ThreadPoolExecutor(max_workers=1)` で `handle.read_pipe()` を実行し、`slot.buffer[:transferred] = payload` でコピーする。 |

### 3.5 Non-goals

```text
- 現行 D3xxAsyncBackend の削除
- native fast path の default 化
- fast path 実装そのもの
- GUI、audio、recording、old DS、old 3DS、非 N3DSXL device の実装
- 未知 VID/PID/product string の device への command 送信
- PyD3XX private internals への依存を無検証で public contract とみなすこと
- Phase 1 前の zero-copy / direct RawFrameSlot write
```

## 4. 実装仕様

### 4.1 Proposed Module Boundary

```text
src/py3dscapture/transport/d3xx_native.py
  D3xxNativeApi
  D3xxNativeApiUnavailable
  NativeOverlapped
  NativeBufferSlot

src/py3dscapture/transport/d3xx_native_streaming.py
  D3xxNativeFastPathBackend
  D3xxNativeFastPathConfigError
  D3xxNativeFastPathReleasedError
  D3xxNativeFastPathCancellingError
```

`d3xx_native.py` は D3XX DLL と native resource lifecycle を閉じ込める。`d3xx_native_streaming.py` は `AsyncTransferBackend` surface に合わせ、`StreamingEngine` には existing backend と同じ callback contract だけを見せる。

Fast path backend 本体は PyD3XX private `_DLL` / `_Handle` を直接参照しない。PyD3XX 由来 DLL / handle を使う場合も `D3xxNativeApi.from_pyd3xx_handle()` 相当の adapter に閉じ込め、将来 system DLL や別 binding へ差し替えられる形にする。

#### 4.1.1 Native API Calling Convention

Current target は 64-bit Windows + `FTD3XX.dll` である。`D3xxNativeApi` は `ctypes.WinDLL` function に `argtypes` / `restype` を明示し、ctypes の implicit integer / pointer conversion に依存しない。

| Function | ctypes surface | 扱い |
| -------- | -------------- | ---- |
| `FT_ReadPipeEx` | `FT_STATUS(FT_HANDLE, UCHAR, PUCHAR, ULONG, PULONG, LPOVERLAPPED)` | `FT_OK` は immediate completion、`FT_IO_PENDING` は pending。その他は error として `FT_AbortPipe` 対象にする。 |
| `FT_GetOverlappedResult` | `FT_STATUS(FT_HANDLE, LPOVERLAPPED, PULONG, BOOL)` | `bWait=False` は poll 用。`FT_IO_INCOMPLETE` は未完了であり error counter へ直行させない。shutdown path では無期限 block を避ける。 |
| `FT_InitializeOverlapped` | `FT_STATUS(FT_HANDLE, LPOVERLAPPED)` | slot ごとに submit 前に 1 回初期化する。 |
| `FT_ReleaseOverlapped` | `FT_STATUS(FT_HANDLE, LPOVERLAPPED)` | pending completion がないことを drain で確認してから呼ぶ。 |
| `FT_AbortPipe` | `FT_STATUS(FT_HANDLE, UCHAR)` | shutdown / native error 時に対象 IN endpoint の pending transfer を cancel する。 |
| `FT_SetStreamPipe` | `FT_STATUS(FT_HANDLE, BOOL, BOOL, UCHAR, ULONG)` | submit 開始前に fixed-size stream pipe を設定する。 |

`NativeOverlapped` は Windows `OVERLAPPED` の layout を Python 側で定義する。64-bit Windows では `sizeof(NativeOverlapped) == 32`、`hEvent` offset は 24 とする。32-bit Python / DLL を対象にする場合は別 gate で layout を再確認する。

### 4.2 Backend Interface

```python
backend = D3xxNativeFastPathBackend(
    handle,
    native_api=native_api,
    pipe=N3DSXL_BULK_IN_ENDPOINT,
    slot_count=2,
    timeout_ms=500,
)
```

予定する制約:

| 項目 | 制約 |
| ---- | ---- |
| `slot_count` | `StreamingEngine.raw_slots` と同じ数を基本にする。実装初期は 2 を推奨する。 |
| `timeout_ms` | current D3XX default と同じ 500ms から開始する。 |
| native API | direct DLL surface がない場合は backend 作成時に失敗する。 |
| handle ownership | protocol / session が開いた `D3xxHandle` を使うが、native backend は close owner ではなく release 時に現行 backend と同じ ownership rule を明示する。 |
| callback | `callback(slot.index, transferred, status, completed_ns)` の既存 shape を維持する。 |

### 4.3 Native Buffer Owner

```python
@dataclass(slots=True)
class NativeReadSlot:
    slot_index: int
    raw_slot: RawFrameSlot
    buffer: ctypes.Array[ctypes.c_char]
    overlapped: NativeOverlapped
    in_flight: bool = False
    submitted_ns: int | None = None
    backend_started_ns: int | None = None
```

Phase 1 では `buffer` を backend-owned native buffer とし、completion 後に `raw_slot.buffer[:transferred] = buffer.raw[:transferred]` を行う。Phase 2 では `raw_slot.buffer` を direct native write target にできるかを別 test で検証する。

### 4.4 Completion Pump

```text
submit_read(slot)
  - reject if released / cancelling
  - locate NativeReadSlot for slot.index
  - mark submitted_ns / backend_started_ns
  - call FT_ReadPipeEx(handle, pipe, buffer, length, transferred_ptr, overlapped_ptr)
  - mark in_flight

completion pump
  - wait for native completion event or poll FT_GetOverlappedResult
  - copy Phase 1 buffer to RawFrameSlot.buffer
  - set transferred/status/completed_ns
  - mark not in_flight
  - invoke callback

cancel_all()
  - stop accepting submits
  - call FT_AbortPipe for the read endpoint
  - wake completion pump

drain()
  - bounded wait until no NativeReadSlot is in_flight
  - poll FT_GetOverlappedResult without indefinite blocking

release()
  - cancel_all()
  - drain()
  - release overlapped / event resources
  - close handle according to ownership rule
```

### 4.5 Timing Metrics

Native backend は `local_021` と同じ timestamp contract を満たす。

| Timestamp | 記録位置 | 用途 |
| --------- | -------- | ---- |
| `submitted_ns` | `StreamingEngine._submit_slot()` | submit-to-complete |
| `backend_started_ns` | native `FT_ReadPipeEx` submit 直前 | backend queue wait、read duration |
| `completed_ns` | completion pump が native completion を確認した時刻 | read duration、completion interval、queue wait |

追加 metric は最初の実装では増やさない。必要なら `native_submit_ms`、`native_completion_wait_ms` を後続 Work Unit で opt-in に追加する。

### 4.6 Safety Rules

| Risk | Rule |
| ---- | ---- |
| buffer use-after-free | native buffer、overlapped、event handle は completion / cancel drain 完了まで owner が参照保持する。 |
| Python buffer resize | Phase 2 direct write では `RawFrameSlot.buffer` を resize しない invariant を test で固定する。 |
| handle close race | `release()` は pending completion drain 後に handle close へ進む。 |
| silent fallback | native API unavailable は config error にし、sequential backend への自動切替は呼び出し側の明示判断にする。 |
| callback overload | completion pump callback では decode、Pillow 変換、blocking queue put、同期 libusb API 呼び出しをしない。 |
| device safety | 既存 D3XX backend の VID/PID/product string guard を通った `D3xxHandle` だけを受け取る。 |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| `D3xxNativeApi` | DLL surface 不足時の失敗 | fake binding without `_DLL` | `D3xxNativeApiUnavailable` |
| `NativeOverlapped` | ABI layout | 64-bit Windows | size / offset が固定値と一致する |
| `D3xxNativeApi` | function signature | fake WinDLL function | `argtypes` / `restype` が固定される |
| completion pump | pending status | fake `FT_IO_PENDING` -> `FT_IO_INCOMPLETE` -> `FT_OK` | pending を error 扱いせず完了まで待つ |
| `NativeReadSlot` | owner lifetime | fake overlapped pending | completion まで buffer / overlapped が release されない |
| `D3xxNativeFastPathBackend.submit_read()` | allocation contract | 2 slots, 10 completions | start 後の native buffer allocation count が増えない |
| completion pump | successful completion | fake native completion | callback が transferred/status/timestamp を受ける |
| engine integration | short transfer | transferred short | decode されず `dropped_raw` |
| engine integration | native error | status non-zero | decode されず `usb_errors` |
| shutdown | cancel / drain / release order | pending read あり | abort/cancel、drain、release の順で呼ばれる |
| timing | `collect_timing=True` | fake completion sequence | `read_duration_ms` など既存 summary key が出る |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| native backend smoke | 10 秒 D3XX timing smoke | N3DSXL 実機、D3XX driver、承認済み command | `usb_errors=0`、`decode_errors=0`、short/drop が説明可能 |
| native backend performance | 60 秒 performance smoke | N3DSXL 実機、D3XX driver、承認済み command | sequential low-latency baseline と同等以上の stability |
| baseline comparison | sequential vs native | 同一実機、同一 raw_slots / poll interval | fps ではなく timing p95 / p99 と shutdown で比較 |

### 検証コマンド

Local design / implementation gates:

```console
uv run pytest tests/unit/test_d3xx_native_streaming_backend.py tests/unit/test_streaming_engine_fake_async.py tests/unit/test_streaming_performance_stats.py -q
uv run ruff check src tests
uv run ty check --no-progress
git diff --check
```

Hardware-gated command scope:

```console
$env:PONKAN_RUN_N3DSXL = "1"
$env:PONKAN_HARDWARE_APPROVED = "1"
$env:PONKAN_N3DSXL_DRIVER_SERVICE = "FTDIBUS3"
uv run pytest tests/e2e/test_n3dsxl_d3xx_native_streaming.py -q

$env:PONKAN_RUN_PERFORMANCE = "1"
uv run pytest tests/performance/test_n3dsxl_d3xx_native_streaming_smoke.py -q
```

Hardware gate の合否は fps 単独では判定しない。少なくとも次を見る。

| 指標 | 合否判断 |
| ---- | -------- |
| `usb_errors` | 0 |
| `decode_errors` | 0 |
| short/drop | 件数と理由が説明可能 |
| `completion_interval_ms.p99` | 59.834Hz の frame period 16.7129ms から異常に伸びない |
| `submit_to_complete_ms.p95/p99` | sequential low-latency baseline と同等か、悪化する場合は default 採用しない理由として記録する |
| `completion_queue_wait_ms.p95/p99` | poll interval / wakeup 設計に見合う |
| shutdown | bounded。pending overlapped leak がない |

### 5.1 Gate Results

| gate | result | evidence |
| ---- | ------ | -------- |
| Unit | pass | `uv run pytest tests/unit -q`: 103 passed |
| Ruff format | pass | `uv run ruff format --check .`: 67 files already formatted |
| Ruff check | pass | `uv run ruff check .`: All checks passed |
| Ty | pass | `uv run ty check --no-progress`: All checks passed |
| Diff whitespace | pass | `git diff --check` |
| Hardware listing | pass | D3XX candidate `0x0403:0x601e product=N3DSXL.2 serial=nxl530228 flags=4` |
| Native timing smoke | pass | `uv run pytest tests/e2e/test_n3dsxl_d3xx_native_streaming.py -q --basetemp artifacts\n3dsxl\20260609-015004\pytest-native-e2e`: 1 passed |
| Native performance smoke | pass | `uv run pytest tests/performance/test_n3dsxl_d3xx_native_streaming_smoke.py -q --basetemp artifacts\n3dsxl\20260609-015030\pytest-native-performance`: 1 passed |
| Native timing artifact | pass | `artifacts\n3dsxl\20260609-015237\3dsxl\native-timing-smoke-readable\stream_stats.json`: `delivered_fps=59.7`, `usb_errors=0`, `decode_errors=0`, `dropped_raw=1`, `shutdown_seconds=0.20248430001083761` |
| Native performance artifact | pass | `artifacts\n3dsxl\20260609-015307\3dsxl\native-performance-smoke-readable\stream_stats.json`: `delivered_fps=59.81666666666667`, `usb_errors=0`, `decode_errors=0`, `dropped_raw=1`, `shutdown_seconds=0.20255759998690337` |

Native 60 秒 artifact の主要 timing は次の通り。

| metric | p95 | p99 | mean |
| ------ | --- | --- | ---- |
| `completion_interval_ms` | 17.99688 | 18.525471999999997 | 16.714131011423795 |
| `submit_to_complete_ms` | 33.180265 | 33.932206 | 30.897594679665737 |
| `completion_queue_wait_ms` | 4.411219999999995 | 4.509722 | 1.9405650417827298 |

`local_021` の sequential low-latency 60 秒 baseline は `delivered_fps=59.8`、`usb_errors=0`、`decode_errors=0`、`completion_interval_ms.p99=16.8987ms`、`submit_to_complete_ms.p99=32.8708ms` だった。今回の native fast path は stability gate を満たしたが、submit-to-complete p99 は約 1.06ms 悪化したため、default backend へ昇格しない。opt-in backend として実装を残し、Phase 2 direct slot write / completion event wait の検証は別 Work Unit 候補にする。

## 6. 実装チェックリスト

- [x] Native fast path backend の目的と非対象を固定する。
- [x] current sequential backend の queue / copy / wakeup を明文化する。
- [x] Phase 0 / Phase 1 / Phase 2 の段階的実装方針を固定する。
- [x] source audit item を記録する。
- [x] TDD Test List を作成する。
- [x] hardware-gated test scope と合否基準を記録する。
- [x] native binding 分離、calling convention、Phase 中間実装の破棄方針を記録する。
- [x] 実装 Work Unit で `D3xxNativeApi` fake test を作成する。
- [x] 実装 Work Unit で opt-in native backend を作成する。
- [x] 実装 Work Unit で実機 timing smoke を実行する。
- [x] 実装 Work Unit で sequential low-latency baseline と比較する。

## 7. Design Decision

Native fast path は opt-in backend として実装したが、現時点で default へ入れる理由はない。`local_021` の低遅延 default は 60 秒実機 smoke で安定し、host pipeline latency は約 2 frame 規模まで下がっている。

今回の実装では native API wrapper と fake native lifecycle test を作り、`FT_ReadPipeEx` / overlapped / cancel / release の境界を unit test で固定した。Direct DLL の function / handle surface は `D3xxNativeApi` に分離し、backend 本体から PyD3XX private internals を直接参照しない。

Hardware smoke は Phase 1 の backend-owned native buffer で実行した。direct `RawFrameSlot.buffer` write は Phase 2 として分離し、今回の production path には入れない。Phase 0 / Phase 1 の途中で作った prototype や重複 helper は、採用済みの native binding boundary へ統合または削除する。中間実装を互換 surface として残さないことで、fast path 検証後のコードベース膨張を防ぐ。
