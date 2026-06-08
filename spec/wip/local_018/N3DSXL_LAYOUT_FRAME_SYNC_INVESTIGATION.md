# N3DSXL Layout Frame Sync Investigation 仕様書

更新日: 2026-06-08

## 1. 概要

### 1.1 目的

`local_012` の manual visual artifact で承認可能な decoder candidate が得られなかったため、N3DSXL 2D raw video の表示変換、screen split、frame boundary / 同期処理を切り分けて調査する。

この仕様は decoder を推測で固定しないための調査 Work Unit である。承認できる表示結果が得られるまで、既存 `decoder_version` は `pending` のまま扱う。

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

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| decoder approval | `manual_visual_status=pending`、承認 candidate なし | 承認済み `decoder_version` を固定、または blocker を明文化 |
| 原因切り分け | 表示変換、screen split、frame boundary が混在 | 各仮説を独立した probe / test / source audit item に分離 |
| raw fixture 価値 | artifact はあるが表示回帰には使えない | approved fixture か investigation evidence として使える |
| streaming への影響 | streaming は動くが表示正当性は未確定 | public frame delivery の表示変換前提を安全に決める |

### 1.5 着手条件

- [x] `spec/complete/local_012/N3DSXL_RAW_CAPTURE_FIXTURE_AND_DECODER.md` の raw fixture と manual visual artifact が生成済み。
- [x] `artifacts\n3dsxl\20260608-185720\pytest-e2e\test_n3dsxl_raw_capture_fixtur0\raw_2d_001.bin` と `.json` が存在する。
- [x] `artifacts\n3dsxl\20260608-191353\manual-visual\manual_visual_manifest.json` に `selected_decoder_version=null` が残っている。
- [x] 既存 decoder が raw read 開始位置と split 境界を仮定していることを確認済み。

### 1.6 Work Unit メタデータ

| 項目 | 内容 |
| ---- | ---- |
| 配置 | `spec/wip/local_018/N3DSXL_LAYOUT_FRAME_SYNC_INVESTIGATION.md` |
| 対応 Step | Step 6 follow-up: decoder approval、Step 7 follow-up: streaming frame boundary evidence |
| 前提 Work Unit | `spec/complete/local_012/N3DSXL_RAW_CAPTURE_FIXTURE_AND_DECODER.md`、`spec/complete/local_013/N3DSXL_ASYNC_STREAMING_ENGINE.md` |
| local task | source audit、fixture probe generator、candidate manifest 拡張、decoder characterization |
| hardware task | 必要時のみ追加 raw capture / streaming raw sample を実行。既存 artifact 調査を先に行う |
| 選択条件 | manual visual artifact が承認不能で、表示変換または frame sync のどちらが原因か未確定のとき |
| 完了証拠 | approved decoder version、または source / hardware blocker と再現 artifact が仕様に残る |

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_018/N3DSXL_LAYOUT_FRAME_SYNC_INVESTIGATION.md` | 新規 | 表示変換・frame sync 不具合調査の作業仕様を定義する。 |
| `spec/complete/local_012/N3DSXL_RAW_CAPTURE_FIXTURE_AND_DECODER.md` | 修正 | manual visual self-check 失敗と local_018 への引き継ぎを追記する。 |
| `spec/complete/local_008/WORK_UNIT_INDEX.md` | 修正 | `local_018` が未完了追跡 Work Unit であることを索引に反映する。 |
| `src/py3dscapture/protocol/layout_3ds.py` | 修正候補 | approved transform が得られた場合だけ decoder version を更新する。 |
| `src/py3dscapture/tools/raw_to_png.py` | 修正候補 | split / roll / source-order probe と manifest evidence を追加する。 |
| `tests/unit/test_layout_3ds_decoder.py` | 修正候補 | approved fixture または probe generator の回帰テストを追加する。 |
| `tests/manual/test_n3dsxl_decoder_visual.py` | 修正候補 | manual approval manifest に selected candidate と根拠を記録できるようにする。 |
| `src/py3dscapture/protocol/n3dsxl.py` | 調査候補 | sync read sequence、drain、stream setup、payload slicing の前提を確認する。 |
| `src/py3dscapture/streaming/engine.py` | 調査候補 | streaming raw completion の frame boundary と sequence evidence を確認する。 |

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
| todo | manual visual manifest が `selected_decoder_version=null` の failure evidence を保持する | characterization | 3.1 | 既存 manifest 読み取り |
| todo | probe generator が split order と source orientation を manifest に列挙する | new behavior | 3.1 | 実機不要 |
| todo | probe generator が row-aligned cyclic roll 候補を出力する | new behavior | 3.1 | frame boundary 仮説 |
| todo | approved candidate がない場合、decoder default を変更しない | regression | 3.1 | 誤った固定を防ぐ |
| todo | approved fixture が得られた場合、top/bottom shape と selected decoder version を回帰固定する | characterization | 3.1 | approval 後に green 化 |
| todo | sync read の transferred / video_size / capture_size evidence を frame boundary 調査 manifest に残す | hardware | 3.1 | 追加実機承認が必要な場合 |

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
| display transform | cc3dsfs display / conversion path | 未監査。単純な 4 candidate では承認不可 |
| frame boundary / sync | `source/CaptureDeviceSpecific/3DSCapture_FTD3/*acquisition*` と streaming setup path | 未監査。raw read 先頭が frame 先頭である保証を確認する |

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

### 4.4 完了判定

| 判定 | 必須 evidence |
| ---- | ------------- |
| approved decoder | selected probe / decoder version、manual visual approval、PNG path、metadata 更新方針 |
| source blocker | cc3dsfs 原典の未監査箇所、確認できなかった前提、次に読むべき file / function |
| hardware blocker | 追加実機 command scope、device identity、artifact path、承認が必要な理由 |
| no-change safety | approved 前に public decoder default を変更していないこと |

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| manifest parser | pending failure evidence | `manual_visual_manifest.json` | `selected_decoder_version is None` |
| probe manifest | split / roll probe metadata | fixture path | probe id、offset、transform、outputs が残る |
| decoder default | 未承認状態 | pending manifest | 既存 default を変更しない |
| approved fixture | 承認後 raw fixture | selected decoder version | top/bottom shape と approval metadata が一致 |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| manual visual probe | 既存 raw fixture から probe PNG を生成 | Pillow extra、raw fixture | manifest と PNG が生成される |
| source audit | cc3dsfs display / acquisition path を読む | network または local checkout | 事実、仮説、未検証事項が仕様に残る |
| hardware recapture | 追加 raw sample で再現性を見る | 明示承認、N3DSXL 実機 | artifact と metadata が残る |

### 検証コマンド

```console
uv run pytest tests/manual -q
uv run pytest tests/unit/test_layout_3ds_decoder.py -q
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
- [ ] cc3dsfs display / acquisition path を source audit する。
- [ ] 既存 raw fixture で split / roll / channel-order probe を追加する。
- [ ] 承認候補が得られた場合、decoder version と manifest 更新を TDD で固定する。
- [ ] 承認候補が得られない場合、frame sync / hardware recapture の blocker を記録する。
- [ ] 必要な検証コマンドを実行し、結果を仕様へ反映する。

## 7. 現時点の観測

| Artifact | 観測 | 判定 |
| -------- | ---- | ---- |
| `artifacts\n3dsxl\20260608-191353\manual-visual\candidate_0_top.png` / `candidate_0_bottom.png` | top / bottom が別々に復元されていない疑い。orientation は完全には確定できない | reject |
| `candidate_1_*` | `candidate_0` と実質同系統。承認可能な改善なし | reject |
| `candidate_2_*` | mirrored / reversed に見える | reject |
| `candidate_3_*` | `candidate_0` と同系統。承認可能な改善なし | reject |
| `artifacts\n3dsxl\20260608-191353\manual-visual-layout-probe\layout_probe_contact.png` | split / source order 追加 probe でも明確な承認候補なし | inconclusive |
| `artifacts\n3dsxl\20260608-191353\manual-visual-layout-probe\roll_probe_contact.png` | row-aligned roll 候補でも明確な承認候補なし | inconclusive |

現時点では、単純な表示変換だけで解ける不具合として扱わない。screen split、raw payload の frame boundary、または acquisition / display path の未監査前提が原因候補である。
