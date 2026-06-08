# N3DSXL Layout Frame Sync Investigation 仕様書

更新日: 2026-06-08

## 1. 概要

### 1.1 目的

`local_012` の manual visual artifact で承認可能な decoder candidate が得られなかったため、N3DSXL 2D raw video の表示変換、screen split、frame boundary / 同期処理を切り分けて調査する。

調査の結果、問題の主因は frame boundary ではなく、N3DSXL FTD3 2D raw layout が単純な `top 0:400 / bottom 400:720` split ではないことだった。`cc3dsfs` の `ftd3_convertVideoToOutput()` と display crop / rotation path に合わせ、調査上の承認 candidate として `decoder_version=4` を一旦固定する。

ただし `decoder_version` は manual visual 調査用 candidate ID であり、production decoder API の長期設計ではない。production path から `decoder_version` 引数を削除し、調査用 candidate を tools/probe 側へ隔離する後続 cleanup は `spec/complete/local_019/N3DSXL_DECODER_API_CLEANUP.md` で完了済み。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| Manual Visual Failure | PNG artifact を人間または VLM が確認した結果、向き、色順、画面分割のいずれかで承認できない状態。 |
| Display Transform | raw RGB8 source から最終表示向きへ変換する transpose / rotate / flip / channel order の組。 |
| Screen Split | 2D raw video の `240 * (400 + 320) * 3` 領域から top / bottom source を切り出す境界と順序。 |
| Frame Boundary | bulk read payload の先頭が 1 frame の video 領域先頭と一致しているという前提。 |
| Frame Sync | connect / stream setup / read sequence によって frame boundary を安定させる処理。 |
| Decoder Candidate | raw fixture から PNG を出力し、manual visual gate で比較する decoder variant。 |

### 1.3 背景・問題

2026-06-08 に `tests/manual/test_n3dsxl_decoder_visual.py` で `raw_2d_001.bin` から candidate PNG 8 件を生成した。user observation と VLM self-check では、出力は上下反転しているように見え、さらに上画面と下画面が重なったような描画になっていた。

現行 decoder は `video_size == 518400` bytes を `np.frombuffer(...).reshape((720, 240, 3))` とし、`0:400` を top、`400:720` を bottom としてから 4 種類の transpose / rotate / flip 候補を出す。これは shape と artifact 生成の bring-up には有効だったが、screen split と frame boundary の正しさまでは証明していない。

初期仕様にも `2D raw layout の正確な screen split / rotate / flip` は open question として残っている。`cc3dsfs` 原典の capture struct / size からは 2D video size までは確認済みだが、display path と acquisition path の同期前提は追加 source audit が必要である。

`cc3dsfs` source audit で、FTD3 2D path は raw 先頭 `(TOP_WIDTH_3DS - BOT_WIDTH_3DS) * HEIGHT_3DS` pixel を top-only 領域として扱い、その後の 640 source rows を bottom / top に 1 row ずつ deinterleave していた。Python 側もこの順序に合わせたところ、既存 fixture から上画面・下画面を別々に読める PNG が得られた。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| decoder approval | `manual_visual_status=pending`、承認 candidate なし | `decoder_version=4` を approved candidate として manifest に記録 |
| 原因切り分け | 表示変換、screen split、frame boundary が混在 | cc3dsfs FTD3 2D deinterleave 漏れとして切り分け済み |
| raw fixture 価値 | artifact はあるが表示回帰には使えない | approved fixture として unit / manual visual evidence に使用 |
| streaming への影響 | streaming は動くが表示正当性は未確定 | local_018 では暫定的に approved candidate へ切替。local_019 で引数なし default decoder へ整理 |
| API cleanup | 調査用 `decoder_version` が production path に露出 | `local_019` で production API から削除済み |

### 1.5 着手条件

- [x] `spec/complete/local_012/N3DSXL_RAW_CAPTURE_FIXTURE_AND_DECODER.md` の raw fixture と manual visual artifact が生成済み。
- [x] `artifacts\n3dsxl\20260608-185720\pytest-e2e\test_n3dsxl_raw_capture_fixtur0\raw_2d_001.bin` と `.json` が存在する。
- [x] `artifacts\n3dsxl\20260608-191353\manual-visual\manual_visual_manifest.json` に `selected_decoder_version=null` が残っている。
- [x] 既存 decoder が raw read 開始位置と split 境界を仮定していることを確認済み。

### 1.6 Work Unit メタデータ

| 項目 | 内容 |
| ---- | ---- |
| 配置 | `spec/complete/local_018/N3DSXL_LAYOUT_FRAME_SYNC_INVESTIGATION.md` |
| 対応 Step | Step 6 follow-up: decoder approval、Step 7 follow-up: streaming frame boundary evidence |
| 前提 Work Unit | `spec/complete/local_012/N3DSXL_RAW_CAPTURE_FIXTURE_AND_DECODER.md`、`spec/complete/local_013/N3DSXL_ASYNC_STREAMING_ENGINE.md` |
| local task | source audit、fixture probe、candidate manifest 拡張、decoder characterization |
| hardware task | 追加実機 capture は不要。既存 artifact で approved decoder を確認 |
| 選択条件 | manual visual artifact が承認不能で、表示変換または frame sync のどちらが原因か未確定のとき |
| 完了証拠 | `decoder_version=4`、approved manifest、unit tests、manual visual artifact |
| 後続 Work Unit | `spec/complete/local_019/N3DSXL_DECODER_API_CLEANUP.md` |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/complete/local_018/N3DSXL_LAYOUT_FRAME_SYNC_INVESTIGATION.md` | 完了移動 | 表示変換・frame sync 不具合調査の結果を記録する。 |
| `spec/complete/local_012/N3DSXL_RAW_CAPTURE_FIXTURE_AND_DECODER.md` | 修正 | local_018 で decoder approval が完了したことを追記する。 |
| `spec/complete/local_008/WORK_UNIT_INDEX.md` | 修正 | `local_018` を完了 Work Unit として索引に反映する。 |
| `src/py3dscapture/protocol/layout_3ds.py` | 修正 | `decoder_version=4` と cc3dsfs FTD3 2D deinterleave を追加する。 |
| `src/py3dscapture/tools/raw_to_png.py` | 修正 | approved manifest と selected decoder evidence を記録できるようにする。 |
| `tests/unit/test_layout_3ds_decoder.py` | 修正 | approved decoder と manifest selection の回帰テストを追加する。 |
| `tests/manual/test_n3dsxl_decoder_visual.py` | 修正 | candidate 4 を manual visual artifact 対象に含める。 |
| `src/py3dscapture/streaming/engine.py` | 修正 | streaming default decoder を `decoder_version=4` に切り替える。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| manual visual failure を記録する | 既存 artifact と観測結果 | 承認済み decoder と誤認せず `pending` のまま残す | `local_012` 追記 |
| source audit を行う | cc3dsfs display / acquisition path | size 事実、transform 仮説、frame boundary 仮説を分けて記録する | 原典 URL または path 必須 |
| split 候補を出す | `raw_2d_001.bin` と metadata | top/bottom 順序、split 境界、source orientation の候補 PNG を生成できる | 実装前に fixture-only |
| roll 候補を出す | raw video bytes と byte/row offset | cyclic offset が frame boundary ずれを改善するか比較できる | 推測固定は禁止 |
| frame sync を切り分ける | sync read / streaming raw sample | read payload 先頭が video frame 先頭か、再 capture で再現するか判断できる | 実機追加は承認必須 |
| decoder を固定する | manual visual approved candidate | `decoder_version` と `manual_visual_status=approved` を metadata / spec に残す | 承認なしで既定化しない |
| blocker を固定する | どの candidate も不成立 | source gap、追加 artifact、実機 command scope を明文化する | 次 Work Unit へ渡せる形にする |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| green | manual visual manifest が `selected_decoder_version=null` の failure evidence を保持する | characterization | 3.1 | 既存 manifest と default pending 出力 |
| green | cc3dsfs FTD3 2D deinterleave で top/bottom shape と内容を分離する | characterization | 3.1 | `decoder_version=4` |
| green | approved candidate を manifest に `selected_decoder_version=4` として記録する | new behavior | 3.1 | `raw_to_png` CLI |
| green | streaming default decoder が approved layout を使う | regression | 3.1 | `tests/unit/test_streaming_engine_fake_async.py` |
| deferred | row-aligned cyclic roll 候補を恒久 CLI として出力する | investigation | 3.1 | 既存 artifact で frame boundary 主因ではないと判断 |
| not-needed | sync read の transferred / video_size / capture_size evidence を frame boundary 調査 manifest に残す | hardware | 3.1 | 追加実機 capture 不要 |

### 3.3 設計方針

調査は仮説を分けて進める。

| 仮説 | 判定方法 | 結果の扱い |
| ---- | -------- | ---------- |
| 表示変換だけが誤っている | 同じ split で rotate / flip / transpose / channel order 候補を追加比較 | 承認候補があれば decoder version を追加 |
| screen split が誤っている | top / bottom 順序、split 位置、source stack order を変えた probe を出す | split 仕様を decoder に反映 |
| frame boundary がずれている | row-aligned roll、byte offset、複数 raw sample の再現性を比較 | acquisition / sync sequence を調査 |
| source data が mixed frame | 連続 capture / streaming raw sample で同じ overlap が出るか確認 | frame sync / in-flight buffer lifecycle を調査 |
| color order が誤っている | RGB / BGR / channel permutation を probe に含める | orientation と独立して判断 |

この Work Unit では、見た目が「まし」な candidate を承認済みとして扱わない。manual visual gate の承認条件は、上下画面が別々に読めること、UI 文字や画面境界が破綻していないこと、top / bottom の内容が入れ替わっていないこと、色順が自然であることとする。

Source Audit:

| 項目 | 参照元 | 状態 |
| ---- | ------ | ---- |
| 2D video size | `include/hw_defs.hpp`、`include/capture_structs.hpp`、`spec/initial/cc3dsfs_python_rebuild_spec.md` | 確定。`240 * (400 + 320) * 3 = 518400` |
| capture struct slicing | `include/capture_structs.hpp`、`src/py3dscapture/protocol/sizes.py` | 確定。payload 先頭 `video_size` bytes を video region として扱う |
| FTD3 2D raw constants | `include/hw_defs.hpp` | 確定。`IN_VIDEO_WIDTH_3DS = HEIGHT_3DS`、`IN_VIDEO_HEIGHT_3DS = TOP_WIDTH_3DS + BOT_WIDTH_3DS`、`IN_VIDEO_NO_BOTTOM_SIZE_3DS = (TOP_WIDTH_3DS - BOT_WIDTH_3DS) * HEIGHT_3DS` |
| FTD3 2D conversion | `source/conversions.cpp` `ftd3_convertVideoToOutput()` | 確定。先頭 80 source rows を top-only とし、残りを bottom/top 交互に deinterleave |
| display crop / rotation | `source/WindowScreen.cpp` `resize_in_rect()` / `crop()`、`source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_shared.cpp` `ftd3_insert_device()` | 確定。`base_rotation=90`、bottom source x=0、top source x=`BOT_WIDTH_3DS` |
| frame boundary / sync | `source/CaptureDeviceSpecific/3DSCapture_FTD3/3dscapture_ftd3_shared.cpp` `data_output_update()` | 確定。`read_data < ftd3_get_video_in_size(is_3d)` は出力せず、既存 artifact の `transferred=520588 >= video_size=518400` と整合 |

## 4. 実装仕様

### 4.1 調査 artifact manifest

probe generator は、PNG だけでなく仮説を機械的に追える manifest を出力する。

```json
{
  "raw_path": "artifacts\\n3dsxl\\...\\raw_2d_001.bin",
  "metadata_path": "artifacts\\n3dsxl\\...\\raw_2d_001.json",
  "manual_visual_status": "pending",
  "failure_summary": "top/bottom overlap suspected; no approved decoder",
  "probes": [
    {
      "probe_id": "split_a",
      "hypothesis": "stacked source top first",
      "byte_offset": 0,
      "screen_order": ["top", "bottom"],
      "transform": "transpose",
      "outputs": [
        {"screen": "top", "path": "split_a_top.png", "width": 400, "height": 240},
        {"screen": "bottom", "path": "split_a_bottom.png", "width": 320, "height": 240}
      ],
      "manual_visual_status": "pending"
    }
  ],
  "selected_probe_id": null
}
```

### 4.2 Decoder approval rule

```python
def approve_decoder_candidate(
    *,
    probe_id: str,
    decoder_version: int,
    visual_status: str,
    evidence_path: str,
) -> None:
    if visual_status != "approved":
        raise ValueError("decoder candidate cannot be fixed without manual visual approval")
```

approval 前に `decode_rgb8_2d()` の既定や streaming API の既定表示変換を変更しない。

実装では `raw_to_png` CLI に次を追加する。

```console
--manual-visual-status approved
--selected-decoder-version 4
--approval-evidence artifacts\n3dsxl\20260608-191353\local-018-ftd3-probe\contact.png
```

`selected_decoder_version` は `manual_visual_status=approved` のときだけ許可し、生成済み outputs に存在しない version は拒否する。

### 4.3 Frame boundary 調査

frame boundary が疑われる場合は、実機追加 command の前に既存 raw fixture で次を試す。

```text
1. video region の byte offset を RGB pixel 境界で cyclic roll する。
2. 1 row 相当の 240 * 3 bytes 境界で cyclic roll する。
3. top width / bottom width 境界を source stack 上で動かす。
4. top / bottom の順序を入れ替える。
5. RGB / BGR の channel order を表示変換と独立に比較する。
```

既存 fixture だけで承認できない場合のみ、実機 raw sample の再取得または streaming 中の raw completion 保存を検討する。その際は `@pytest.mark.requires_n3dsxl`、`PONKAN_RUN_N3DSXL=1`、`PONKAN_HARDWARE_APPROVED=1`、artifact 保存先、cleanup を事前に提示する。

今回の原因は source layout 変換漏れであり、追加実機 capture は不要と判断した。既存 artifact の `raw_2d_001.json` は `transferred=520588`、`video_size=518400`、`capture_size=555008` を持ち、`cc3dsfs` の `data_output_update()` と同じ「video size 以上だけ出力する」条件を満たしている。

### 4.4 完了判定

| 判定 | 必須 evidence |
| ---- | ------------- |
| approved decoder | `decoder_version=4`、`manual_visual_status=approved`、PNG path、manifest |
| source blocker | なし。FTD3 2D conversion / display path を監査済み |
| hardware blocker | なし。追加実機 capture 不要 |
| no-change safety | approved manifest 生成後に streaming default を暫定 candidate へ変更。production API cleanup は local_019 で完了済み |

### 4.5 実装結果

| 項目 | 結果 |
| ---- | ---- |
| decoder identity | local_018 時点は `DecoderVersion.FTD3_CC3DSFS_2D = 4`。local_019 以降は `decoder_id="ftd3_cc3dsfs_2d"` |
| source split | `raw.reshape((720, 240, 3))` の先頭 80 rows を top-only、残りを bottom/top 交互に deinterleave |
| display transform | deinterleave 後の source を `np.rot90(source, k=1)` で `(240, width, 3)` に変換 |
| manual visual approved artifact | `artifacts\n3dsxl\20260608-191353\manual-visual-approved\candidate_4_top.png`、`candidate_4_bottom.png` |
| approved manifest | `artifacts\n3dsxl\20260608-191353\manual-visual-approved\manual_visual_manifest.json` |
| approval evidence | `artifacts\n3dsxl\20260608-191353\local-018-ftd3-probe\contact.png` |
| streaming default | local_018 時点は暫定 candidate 呼び出し。local_019 で `_decode_2d_default()` は `decode_rgb8_2d(raw_video)` へ変更済み |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| manifest parser | pending failure evidence | `manual_visual_manifest.json` | `selected_decoder_version is None` |
| probe manifest | split / roll probe metadata | fixture path | probe id、offset、transform、outputs が残る |
| decoder default | approved manifest | `decoder_version=4` | streaming default が approved layout を使う |
| approved fixture | 承認後 raw fixture | selected decoder version | top/bottom shape と approval metadata が一致 |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| manual visual probe | 既存 raw fixture から probe PNG を生成 | Pillow extra、raw fixture | manifest と PNG が生成される |
| source audit | cc3dsfs display / acquisition path を読む | network または local checkout | 事実、仮説、未検証事項が仕様に残る |
| hardware recapture | 追加 raw sample で再現性を見る | 明示承認、N3DSXL 実機 | artifact と metadata が残る |

### 検証コマンド

```console
uv run pytest tests/manual/test_n3dsxl_decoder_visual.py -q
uv run pytest tests/unit/test_layout_3ds_decoder.py -q
uv run pytest tests/unit/test_streaming_engine_fake_async.py -q
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
git diff --check
```

manual visual artifact 再生成:

```console
$env:PONKAN_RUN_MANUAL_VISUAL = "1"
$env:PONKAN_MANUAL_VISUAL_RAW = "artifacts\n3dsxl\20260608-185720\pytest-e2e\test_n3dsxl_raw_capture_fixtur0\raw_2d_001.bin"
$env:PONKAN_MANUAL_VISUAL_METADATA = "artifacts\n3dsxl\20260608-185720\pytest-e2e\test_n3dsxl_raw_capture_fixtur0\raw_2d_001.json"
$env:PONKAN_MANUAL_VISUAL_OUT = "artifacts\n3dsxl\20260608-191353\manual-visual"
uv run --extra image pytest tests/manual/test_n3dsxl_decoder_visual.py -q
```

## 6. 実装チェックリスト

- [x] `local_012` に manual visual self-check failure を追記する。
- [x] 表示変換・screen split・frame boundary を分けた調査仕様を作成する。
- [x] cc3dsfs display / acquisition path を source audit する。
- [x] 既存 raw fixture で cc3dsfs FTD3 deinterleave / rotation probe を追加する。
- [x] 承認候補が得られたため、decoder version と manifest 更新を TDD で固定する。
- [x] 承認候補が得られたため、frame sync / hardware recapture blocker は不要と記録する。
- [x] 必要な検証コマンドを実行し、結果を仕様へ反映する。

## 7. 現時点の観測

| Artifact | 観測 | 判定 |
| -------- | ---- | ---- |
| `artifacts\n3dsxl\20260608-191353\manual-visual\candidate_0_top.png` / `candidate_0_bottom.png` | top / bottom が別々に復元されていない疑い。orientation は完全には確定できない | reject |
| `candidate_1_*` | `candidate_0` と実質同系統。承認可能な改善なし | reject |
| `candidate_2_*` | mirrored / reversed に見える | reject |
| `candidate_3_*` | `candidate_0` と同系統。承認可能な改善なし | reject |
| `artifacts\n3dsxl\20260608-191353\manual-visual-layout-probe\layout_probe_contact.png` | split / source order 追加 probe でも明確な承認候補なし | inconclusive |
| `artifacts\n3dsxl\20260608-191353\manual-visual-layout-probe\roll_probe_contact.png` | row-aligned roll 候補でも明確な承認候補なし | inconclusive |
| `artifacts\n3dsxl\20260608-191353\local-018-ftd3-probe\contact.png` | cc3dsfs FTD3 2D deinterleave 後、`rot_ccw` / `transpose_flip_y` が上画面・下画面を別々に自然な向きで復元 | approved |
| `artifacts\n3dsxl\20260608-191353\manual-visual-approved\candidate_4_top.png` / `candidate_4_bottom.png` | UI 文字、画面境界、色順が自然。top / bottom 入れ替わりなし | approved |

結論として、問題は raw payload の frame boundary ではなく、FTD3 2D source layout の deinterleave 漏れだった。local_018 では `decoder_version=4` を調査上の approved candidate とした。

設計上、`decoder_version` は調査 scaffolding であり production API として残すべきではない。この後始末は `local_019` で完了し、現在の production API は `decode_rgb8_2d(raw_video)`、新規 manifest は `decoder_id="ftd3_cc3dsfs_2d"`、legacy candidate は `raw_to_png --probe-candidates` の明示実行に限定する。

## 8. Gate Results

| Gate | 結果 | Evidence |
| ---- | ---- | -------- |
| Unit | pass | `uv run pytest tests/unit -q`: 84 passed |
| Manual visual default | skip as expected | `uv run pytest tests/manual/test_n3dsxl_decoder_visual.py -q`: 1 skipped。env 未設定時は実行しない |
| Approved artifact generation | pass | local_018 時点の command は `uv run --extra image python -m py3dscapture.tools.raw_to_png ... --manual-visual-status approved --selected-decoder-version 4`。local_019 以降の新規 manifest は `decoder_id` を使う |
| Format | pass | `uv run ruff format --check .`: 61 files already formatted |
| Lint | pass | `uv run ruff check .`: All checks passed |
| Type | pass | `uv run ty check --no-progress`: All checks passed |
| Diff | pass | `git diff --check` |
| Hardware recapture | not run | 既存 fixture と source audit で原因を確定。追加実機 command は不要 |
