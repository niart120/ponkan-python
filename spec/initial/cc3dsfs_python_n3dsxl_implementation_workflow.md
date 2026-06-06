# cc3dsfs Python Rebuild: Implementation Workflow

更新日: 2026-06-07

この文書は、`cc3dsfs_python_n3dsxl_async_streaming_mvp_spec.md` を実装するための作業手順をまとめる。仕様判断はメイン仕様書に置き、この文書では順序、テストゲート、差分レビュー、実装時の制約だけを扱う。

Agentic SDD では、この文書の Step を既定の Work Unit 候補として扱う。Main Agent は `AGENTS.md`、`spec/initial/*`、作業仕様を Constitution として読み、ユーザから追加の Intent Delta がない場合も、この順序と gate に沿って次の Work Unit を選ぶ。

---

# 1. 作業原則

```text
- new 3DS XL を最初の E2E 対象にする
- async high-performance streaming を MVP に含める
- single raw frame path は bring-up / debug 用に残す
- old 3DS は設計枠だけ確保し、new 3DS XL E2E 前に深追いしない
- product string が N3DSXL / N3DSXL.2 でない device に N3DSXL command を送らない
- callback 内で decode、Pillow 変換、blocking 処理を行わない
- unbounded queue を使わない
- stop 時に pending transfer cancel、interface release、handle close を必ず行う
```

---

# 2. Agentic SDD での扱い

```text
- 各 Step は、実装開始前に選択する Work Unit の既定候補である
- Main Agent は、選択した Step または Step 内の TDD item だけを対象にする
- 未選択の Step、device、backend、GUI、audio、recording、old DS は実装しない
- Plan では対象、非対象、影響範囲、実機要否、検証 command を明示する
- Task Graph では blocking task、sidecar task、hardware task を分ける
- sidecar task や観点別 gate がある場合、Main Agent は必要に応じて Subagent を起動する
- Subagent の結果は Main Agent が統合し、gate 報告に採否を残す
- 実機 command は、device identity と実行意図への人間承認があるまで実行しない
```

---

# 3. 実装順

## Step 0: constants and size tests

実装:

```text
- protocol/sizes.py
- devices/n3dsxl_ftd3.py の定数
- tests/unit/test_n3dsxl_constants.py
```

確認:

```bash
uv run pytest tests/unit/test_n3dsxl_constants.py
```

ゲート:

```text
- VID/PID list が仕様と一致する
- accepted product strings が仕様と一致する
- endpoint 番号が仕様と一致する
- video_size_2d = 518400
- video_size_3d = 806400
- capture_size_2d / capture_size_3d を計算できる
```

## Step 1: device listing

実装:

```text
- transport/libusb_backend.py
- tools/list_devices.py
```

確認:

```bash
uv run python -m py3dscapture.tools.list_devices
```

ゲート:

```text
- 実機 new 3DS XL が候補として表示される
- VID/PID/product string を表示できる
- product string 不一致の FTDI device を N3DSXL 候補にしない
```

## Step 2: open / claim / close

実装:

```text
- N3DSXLDevice.open()
- N3DSXLDevice.close()
- interface 0/1 claim/release
```

確認:

```bash
uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_open_close.py
```

ゲート:

```text
- open → claim → close が複数回成功する
- 例外時も release/close が走る
- Ctrl-C 時に handle が残らない
```

## Step 3: FTD3 command pipe

実装:

```text
- transport/ftd3_pipe.py
- create_pipe
- abort_pipe
- set_stream_pipe
- prepare_read_pipe
- prepare_write_pipe
```

確認:

```bash
uv run pytest tests/unit/test_ftd3_pipe_payloads.py
uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_ftd3_pipe.py
```

ゲート:

```text
- command payload unit test が通る
- 実機で create/abort が libusb error なしで返る
- error 時に例外型へ変換される
```

## Step 4: connect sequence

実装:

```text
- protocol/n3dsxl.py
- N3DSXLDevice.connect()
- 2D default stream setup
```

確認:

```bash
uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_connect.py
```

ゲート:

```text
- 2D mode で connect 完了
- 失敗した command と libusb status をログに残す
- 不明な product string では connect しない
```

## Step 5: single raw frame capture

実装:

```text
- N3DSXLDevice.read_raw_frame(mode_3d=False)
- tools/capture_raw.py
```

確認:

```bash
uv run python -m py3dscapture.tools.capture_raw --model new_3ds_xl --out tests/fixtures/n3dsxl/raw_2d_001.bin
```

ゲート:

```text
- raw_2d_001.bin を保存できる
- raw_2d_001.json を保存できる
- transferred >= 518400
- video_size / capture_size / product string / VID / PID が metadata に入る
```

## Step 6: decoder and PNG

実装:

```text
- protocol/layout_3ds.py
- image/frame.py
- tools/raw_to_png.py
```

確認:

```bash
uv run python -m py3dscapture.tools.raw_to_png tests/fixtures/n3dsxl/raw_2d_001.bin --metadata tests/fixtures/n3dsxl/raw_2d_001.json --out tests/fixtures/n3dsxl/
```

ゲート:

```text
- top ndarray shape = (240, 400, 3)
- bottom ndarray shape = (240, 320, 3)
- dtype = uint8
- PNG 出力できる
- 向き・色・画面分割を目視承認できる
- 承認済み decoder_version を metadata に残す
```

## Step 7: async streaming engine

実装:

```text
- transport/libusb_async.py
- streaming/buffers.py
- streaming/engine.py
- streaming/stats.py
- streaming/policies.py
- tools/stream_n3dsxl.py
```

確認:

```bash
uv run pytest -m requires_n3dsxl tests/e2e/test_n3dsxl_streaming.py
uv run python -m py3dscapture.tools.stream_n3dsxl --duration 10 --stats
```

ゲート:

```text
- raw_slots 個の transfer を in-flight にできる
- callback 内で decode しない
- CaptureFrame を iterator で受け取れる
- output queue が詰まっても固まらない
- stats を表示できる
- stop 時に cancel → drain → release できる
```

## Step 8: performance smoke test

確認:

```bash
uv run pytest -m "requires_n3dsxl and performance" tests/performance/test_n3dsxl_streaming_smoke.py
uv run python -m py3dscapture.tools.stream_n3dsxl --duration 60 --noop-consumer --stats
```

ゲート:

```text
- 2D mode で 60 秒 stream できる
- no-op consumer で delivered fps >= 50 を目標に測定できる
- usb_errors = 0
- shutdown <= 2 seconds
- submitted/completed/decoded/delivered/dropped/errors が記録される
```

---

# 4. レビュー観点

```text
constants:
  仕様値と一致しているか。推測値を確定扱いしていないか。

libusb wrapper:
  thin wrapper に留まっているか。protocol logic が混ざっていないか。

FTD3 command pipe:
  command payload unit test があるか。未知 device へ送らない guard があるか。

connect sequence:
  どの command で失敗したか追跡できるか。失敗時 cleanup されるか。

raw capture:
  raw .bin と metadata .json を保存できるか。decoder 前の証拠を残せるか。

decoder:
  raw layout の仮説と承認済み decoder_version が分かれているか。

streaming:
  callback が軽いか。bounded queue か。drop policy が明示されているか。shutdown 安全か。

performance:
  fps だけでなく drop/error/shutdown 時間を記録しているか。
```

---

# 5. 不具合調査時のログ

最低限、以下をログに残す。

```text
- timestamp_ns
- model
- VID/PID
- product string
- interface claim result
- command name
- command payload length
- libusb status
- transferred bytes
- sequence
- raw slot index
- queue size
- drop count
- decoder_version
```

raw frame 取得に成功したら、必ず `.bin` と `.json` を保存する。画像化に失敗しても、raw fixture として残せる状態にする。

---

# 6. AI Agent へ渡す最小指示テンプレート

```text
Agentic SDD で進める。
Constitution は AGENTS.md と spec/initial/*。
対象仕様は cc3dsfs_python_n3dsxl_async_streaming_mvp_spec.md。
今回の Work Unit は <Step名またはTDD item> だけ。
未選択の Step を実装しない。
old 3DS、old DS、Optimize、Nisetro、IS/Partner系、GUI、audio playback、video encoding は実装しない。
product string が N3DSXL / N3DSXL.2 でない device に N3DSXL command を送らない。
callback 内で decode、Pillow 変換、blocking 処理を行わない。
必要に応じて Subagent を起動してよい。
Subagent の結果は Main Agent が統合し、採否を gate 報告に残す。
実機 command は明示承認まで実行しない。
変更後に対象 gate を実行し、失敗内容を示す。
```
