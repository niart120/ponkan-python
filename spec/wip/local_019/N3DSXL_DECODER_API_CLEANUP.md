# N3DSXL Decoder API Cleanup 仕様書

更新日: 2026-06-08

## 1. 概要

### 1.1 目的

`local_018` で承認済み N3DSXL FTD3 2D layout が確定したため、production decoder API から調査用の `decoder_version` 引数と legacy candidate ID を取り除く。

production path は常に cc3dsfs FTD3 2D layout を使い、調査用の複数 candidate は `tools` 側の probe 機能へ隔離する。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| Production Decoder | 利用者 API と streaming default が使う確定済み decoder。N3DSXL FTD3 2D layout だけを扱う。 |
| Probe Candidate | raw layout 調査や visual comparison のために生成する候補画像。production decoder ではない。 |
| Decoder Version | `local_012` / `local_018` で使った数値 candidate ID。production API から削除する対象。 |
| Decoder ID | manifest に残す意味付き識別子。承認済み decoder は `ftd3_cc3dsfs_2d` とする。 |
| Legacy Candidate | `0..3` の単純 split / rotate / flip 候補。過去 artifact の説明用には残すが production API には出さない。 |

### 1.3 背景・問題

`local_012` では raw layout が未確定だったため、`decode_rgb8_2d(raw_video, decoder_version=...)` と `iter_decoder_candidates()` で複数候補を生成し、PNG を目視確認する形にした。

`local_018` で cc3dsfs 原典の `ftd3_convertVideoToOutput()` に合わせた正しい layout が分かったが、実装は既存 candidate ID の延長として `decoder_version=4` を追加した。その結果、調査用 candidate ID が production decoder の既定値として露出している。

これは次の点で不適切である。

| 問題 | 内容 |
| ---- | ---- |
| API leak | 利用者が選ぶ必要のない `decoder_version` が `decode_rgb8_2d()` に必須引数として残る。 |
| 意味の混同 | `decoder_version=4` は互換バージョンではなく、manual visual candidate の番号である。 |
| obsolete candidate | `0..3` は誤った split 前提の比較用候補であり、production path から到達できるべきではない。 |
| manifest drift | `selected_decoder_version` は調査手段の番号で、承認済み decoder の意味を直接表していない。 |

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| production decode API | `decode_rgb8_2d(raw_video, decoder_version=4)` | `decode_rgb8_2d(raw_video)` |
| streaming default | 内部で `decoder_version=4` を指定 | decoder argument なしで approved layout を使用 |
| probe candidate | protocol module の `DecoderVersion` として露出 | `tools` / test helper 側へ隔離 |
| manifest | `selected_decoder_version=4` | `decoder_id="ftd3_cc3dsfs_2d"` |
| legacy candidate | production decoder と同じ enum に混在 | probe 専用・過去 artifact 説明用に限定 |

### 1.5 着手条件

- [x] `spec/complete/local_018/N3DSXL_LAYOUT_FRAME_SYNC_INVESTIGATION.md` が完了済み。
- [x] approved artifact `artifacts\n3dsxl\20260608-191353\manual-visual-approved\candidate_4_top.png` / `candidate_4_bottom.png` が存在する。
- [x] cc3dsfs FTD3 2D deinterleave の source audit が `local_018` に記録済み。
- [x] 既存実装は `fix/local-018-layout-frame-sync` 上で `decoder_version=4` を production default としている。

### 1.6 Work Unit メタデータ

| 項目 | 内容 |
| ---- | ---- |
| 配置 | `spec/wip/local_019/N3DSXL_DECODER_API_CLEANUP.md` |
| 対応 Step | Step 6 follow-up: decoder API cleanup、Step 7 follow-up: streaming default cleanup |
| 前提 Work Unit | `spec/complete/local_018/N3DSXL_LAYOUT_FRAME_SYNC_INVESTIGATION.md` |
| local task | public decoder signature cleanup、probe API isolation、manifest key cleanup、tests update |
| hardware task | 不要。既存 approved artifact と unit / manual visual artifact generation で検証する |
| 選択条件 | approved decoder が確定し、調査用 `decoder_version` が production API に残っているとき |
| 完了証拠 | `decoder_version` 引数が production path から消え、`decoder_id` manifest と regression tests が残る |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `src/py3dscapture/protocol/layout_3ds.py` | 修正 | `decode_rgb8_2d(raw_video)` を approved layout 専用にし、`DecoderVersion` と `iter_decoder_candidates()` を削除または非公開化する。 |
| `src/py3dscapture/streaming/engine.py` | 修正 | `_decode_2d_default()` から `decoder_version` 指定を削除する。 |
| `src/py3dscapture/tools/raw_to_png.py` | 修正 | 通常出力は approved decoder のみ。probe 出力が必要な場合は明示 option と名前付き candidate を使う。 |
| `tests/unit/test_layout_3ds_decoder.py` | 修正 | production decoder は引数なし、approved layout を返すことを固定する。 |
| `tests/unit/test_streaming_engine_fake_async.py` | 修正 | streaming default が引数なし decoder で approved layout を使うことを固定する。 |
| `tests/manual/test_n3dsxl_decoder_visual.py` | 修正 | manual visual artifact の manifest が `decoder_id` を記録することを確認する。 |
| `spec/complete/local_018/N3DSXL_LAYOUT_FRAME_SYNC_INVESTIGATION.md` | 修正 | `decoder_version=4` は調査中の暫定 candidate ID で、local_019 で cleanup することを明記する。 |
| `spec/complete/local_012/N3DSXL_RAW_CAPTURE_FIXTURE_AND_DECODER.md` | 修正 | `decoder_version` 固定という表現を `decoder_id` / approved layout へ置き換える。 |
| `spec/complete/local_008/WORK_UNIT_INDEX.md` | 修正 | `local_019` を未完了 follow-up Work Unit として追加する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| production decode を実行する | 2D raw video bytes | `decode_rgb8_2d(raw_video)` が approved top / bottom `CaptureFrame` を返す | `decoder_version` 引数なし |
| wrong size を拒否する | `video_size(False)` 以外の bytes | `DecodeError` | 既存挙動維持 |
| streaming default decode を実行する | async raw completion | approved layout の frame が output queue に入る | version 指定なし |
| approved PNG を生成する | raw fixture、metadata、out dir | approved top / bottom PNG と manifest を出力 | 通常 path は 1 decoder |
| manifest を記録する | approved PNG generation | `decoder_id="ftd3_cc3dsfs_2d"`、`manual_visual_status` を残す | `selected_decoder_version` は新規 manifest では使わない |
| probe を明示実行する | raw fixture、probe option | legacy/probe candidate PNG を出力する | production API と別経路 |
| legacy candidate を隔離する | `0..3` 相当の比較候補 | protocol public API から直接到達できない | tests も probe 側へ移す |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | `decode_rgb8_2d(raw_video)` が approved FTD3 2D layout を返す | behavior change | 3.1 | 引数削除の red |
| todo | `decode_rgb8_2d(..., decoder_version=4)` が呼べない | API cleanup | 3.1 | `TypeError` または static test |
| todo | streaming default が version 指定なしで approved layout を使う | regression | 3.1 | `test_streaming_engine_fake_async.py` |
| todo | `raw_to_png` 通常実行は approved PNG と `decoder_id` manifest を出す | behavior change | 3.1 | outputs は top/bottom のみ |
| todo | probe option 実行だけが legacy candidates を出す | tool behavior | 3.1 | candidate ID は名前付き |
| todo | 新規 manifest に `selected_decoder_version` が出ない | regression | 3.1 | 過去 artifact は読めてもよい |
| todo | `local_012` / `local_018` の仕様表現が `decoder_version` production 固定を推奨しない | documentation | 3.1 | `rg` で確認 |

### 3.3 設計方針

production と investigation を分ける。

| レイヤー | 方針 |
| -------- | ---- |
| `protocol/layout_3ds.py` | approved decoder のみを持つ。cc3dsfs FTD3 2D deinterleave は private helper とする。 |
| `streaming/engine.py` | decoder policy を知らず、`decode_rgb8_2d(raw_video)` を呼ぶ。 |
| `tools/raw_to_png.py` | 通常は approved PNG を出す。調査用 candidate は `--probe-candidates` のような明示 option に閉じる。 |
| manifest | production result は `decoder_id` を使う。probe result は `probe_id` / `candidate_id` を使う。 |
| tests | production tests と probe tests を分け、legacy candidate を production regression として扱わない。 |

Source Audit:

| 項目 | 参照元 | 状態 |
| ---- | ------ | ---- |
| FTD3 2D deinterleave | `source/conversions.cpp` `ftd3_convertVideoToOutput()` | local_018 で監査済み。今回変更なし |
| display crop / rotation | `source/WindowScreen.cpp`、`3dscapture_ftd3_shared.cpp` | local_018 で監査済み。今回変更なし |
| command / sequence | なし | API cleanup のため新規 command なし |

## 4. 実装仕様

### 4.1 Production Decoder

```python
APPROVED_N3DSXL_2D_DECODER_ID = "ftd3_cc3dsfs_2d"

def decode_rgb8_2d(raw_video: bytes | memoryview) -> CaptureFrame:
    ...
```

`decoder_version` は引数から削除する。`DecodeError` と shape / dtype contract は維持する。

### 4.2 Probe Candidate

probe candidate は production module の public enum ではなく、tools 内部または private helper として扱う。

```python
ProbeCandidateId = Literal[
    "legacy_top_first_transpose",
    "legacy_top_first_rotate_cw",
    "legacy_top_first_rotate_cw_flip_x",
    "ftd3_cc3dsfs_2d",
]
```

名前は意味を持つ文字列にし、番号だけの candidate ID は新規 manifest に出さない。

### 4.3 Manifest

通常出力:

```json
{
  "raw_path": "artifacts\\n3dsxl\\...\\raw_2d_001.bin",
  "metadata_path": "artifacts\\n3dsxl\\...\\raw_2d_001.json",
  "manual_visual_status": "approved",
  "decoder_id": "ftd3_cc3dsfs_2d",
  "outputs": [
    {"screen": "top", "path": "top.png", "width": 400, "height": 240},
    {"screen": "bottom", "path": "bottom.png", "width": 320, "height": 240}
  ]
}
```

probe 出力:

```json
{
  "probe_mode": true,
  "probes": [
    {
      "candidate_id": "legacy_top_first_transpose",
      "hypothesis": "obsolete top-first split",
      "manual_visual_status": "rejected"
    }
  ]
}
```

### 4.4 Backward Compatibility

過去 artifact の `selected_decoder_version` は履歴として残す。新規 manifest では出さない。

`RawCapture.to_metadata()` の `decoder_version: null` は raw capture 時点の metadata であり、今回の production decoder API cleanup とは別扱いにする。必要なら後続で `decoder_id` へ移行するが、この Work Unit の必須範囲は decoded artifact / decoder API に限定する。

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| `decode_rgb8_2d` | approved FTD3 2D layout | synthetic FTD3 raw | top/bottom shape と pixel 分離 |
| `decode_rgb8_2d` | 引数 cleanup | `decoder_version=4` | 呼べない |
| streaming default | approved layout | fake async payload | top/bottom が混ざらない |
| raw_to_png manifest | decoder_id | synthetic raw | `decoder_id="ftd3_cc3dsfs_2d"` |
| raw_to_png manifest | legacy version removal | normal generation | `selected_decoder_version` がない |
| probe mode | legacy candidates | explicit probe option | named candidate outputs |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| manual visual normal | approved PNG を生成 | Pillow extra、既存 raw fixture | top/bottom PNG と `decoder_id` manifest |
| manual visual probe | legacy candidate を比較 | explicit probe option | probe manifest と candidate PNG |
| docs consistency | 仕様が version 固定を推奨しない | `rg decoder_version spec/complete/local_012 spec/complete/local_018 spec/wip/local_019` | historical / cleanup 文脈だけに残る |

### 検証コマンド

```console
uv run pytest tests/unit/test_layout_3ds_decoder.py -q
uv run pytest tests/unit/test_streaming_engine_fake_async.py -q
uv run pytest tests/manual/test_n3dsxl_decoder_visual.py -q
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
git diff --check
```

## 6. 実装チェックリスト

- [ ] `decode_rgb8_2d()` から `decoder_version` 引数を削除する。
- [ ] `DecoderVersion` / `iter_decoder_candidates()` を production API から削除または probe 専用へ移動する。
- [ ] `_decode_2d_default()` を `decode_rgb8_2d(raw_video)` 呼び出しにする。
- [ ] `raw_to_png` の通常出力を approved decoder のみへ変更する。
- [ ] `raw_to_png` の manifest を `decoder_id` へ変更し、新規 manifest から `selected_decoder_version` を削除する。
- [ ] legacy candidates を明示 probe option に隔離する。
- [ ] unit / manual visual tests を production と probe に分けて更新する。
- [ ] `local_012` / `local_018` の `decoder_version` production 固定表現を cleanup 方針に合わせて更新する。
- [ ] 検証コマンドを実行し、結果を仕様へ反映する。
- [ ] レビュー完了。
