# N3DSXL MVP Work Unit Index 仕様書

更新日: 2026-06-07

## 1. 概要

### 1.1 目的

`spec/initial` にある new 3DS XL async streaming MVP を、Agentic SDD が 1 Work Unit ずつ選択できる詳細仕様書群へ分解する。

この文書は索引であり、各 Work Unit の依存関係、gate、実機要否、source audit 要否を一箇所で確認できるようにする。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| Work Unit | Main Agent が一度に選ぶ最小作業単位。実装 Step 1つ、または Step 内の TDD Test List 1項目。 |
| Work Unit Spec | `spec/wip/local_008/` から `spec/wip/local_014/` に 1 仕様書ずつ配置した詳細仕様書。 |
| Bring-up Gate | async streaming 前に通す単発 raw capture、raw 保存、decoder、PNG 目視確認の gate。 |
| MVP Acceptance | continuous async streaming、bounded queue、drop policy、stats、shutdown、performance smoke を含む完了条件。 |
| Source Audit Gate | `cc3dsfs` 由来の定数、USB command、構造体サイズ、sequence を実装前に原典 path / URL とともに固定する gate。 |
| Hardware Gate | new 3DS XL 実機、pytest marker、承認済み command、raw artifact、cleanup を必要とする gate。 |

### 1.3 背景・問題

`spec/initial/cc3dsfs_python_rebuild_spec.md` は MVP 全体像を持ち、`spec/initial/cc3dsfs_python_n3dsxl_implementation_workflow.md` は Step 0-8 の順序を持つ。一方で、Agentic SDD が自律的に次の Work Unit を選ぶには、各 Step の対象ファイル、振る舞い、TDD Test List、source audit、hardware gate、非対象を分けた作業仕様が必要である。

この仕様群では、初期仕様の scope を縮めずに、実装開始時に直接読める詳細仕様へ展開する。各 Work Unit は個別の `local_xxx` ディレクトリに分け、実装完了時に仕様単位で `spec/complete/local_xxx/` へ移せる状態にする。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| Work Unit 選択 | 初期 workflow の Step を都度読み解く | 索引から最初の未完了 Work Unit を選べる |
| scope 境界 | MVP 全体仕様から推測する | 各仕様に対象、非対象、依存、gate を明記する |
| TDD 開始 | Step 単位が大きい | TDD Test List 1項目へ分割できる |
| source audit | 実装時に個別判断 | command、定数、構造体サイズを使う前の gate として扱う |
| 実機安全 | 実行時に注意する | 仕様上の marker、env var、人間承認、artifact、cleanup を必須にする |

### 1.5 着手条件

- [x] `AGENTS.md` に Agentic SDD と実機安全制約がある。
- [x] `spec/initial/cc3dsfs_python_rebuild_spec.md` に MVP scope と非対象がある。
- [x] `spec/initial/cc3dsfs_python_n3dsxl_implementation_workflow.md` に Step 0-8 がある。
- [x] `src/py3dscapture/protocol/sizes.py` と `tests/unit/test_n3dsxl_sizes.py` に Step 0 の現行実装がある。
- [x] Step 1 以降の詳細仕様を Main Agent が読み、1 Work Unit ずつ実装できる。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_008/WORK_UNIT_INDEX.md` | 新規 | Work Unit 仕様群の索引、依存関係、選択規則を定義する。 |
| `spec/complete/local_009/N3DSXL_DEVICE_IDENTITY_AND_SIZES.md` | 完了済み | Step 0 の USB identity、screen size、capture size、既存単体テストを定義する。 |
| `spec/complete/local_010/N3DSXL_DEVICE_DISCOVERY_AND_SESSION.md` | 完了済み | Step 1-2 の device listing、safe open、claim、close を定義する。 |
| `spec/complete/local_011/N3DSXL_FTD3_PIPE_AND_CONNECT.md` | 完了済み | Step 3-4 の FTD3 command pipe と N3DSXL connect sequence を定義する。 |
| `spec/complete/local_012/N3DSXL_RAW_CAPTURE_FIXTURE_AND_DECODER.md` | 完了済み | Step 5-6 の raw frame capture、fixture、decoder、PNG 目視確認を定義する。 |
| `spec/complete/local_013/N3DSXL_ASYNC_STREAMING_ENGINE.md` | 完了済み | Step 7 の async transfer、decode worker、queue、stats、shutdown を定義する。 |
| `spec/wip/local_014/N3DSXL_PERFORMANCE_AND_HARDWARE_GATES.md` | 新規 | Step 8 と実機 gate、performance smoke、artifact 記録を定義する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| Work Unit を選ぶ | Agentic SDD 開始、Intent Delta なし | 依存が満たされた最初の未完了 TDD item を選ぶ | Step 0-8 の順序を既定にする |
| scope を閉じる | Work Unit が選択済み | 未選択の Step、device、backend、GUI、audio、recording、old DS を実装しない | 初期仕様の非対象を継承する |
| gate を宣言する | 実装前 Plan | 検証 command、source audit 要否、hardware 要否を明記する | 実機 command は承認まで実行しない |
| source audit を要求する | cc3dsfs 由来の command / sequence / size を使う | 原典 path / URL と検証状態を仕様または dev-journal に残す | `cc3dsfs-source-audit` を使う |
| hardware gate を止める | requires_n3dsxl command が必要 | device identity、command scope、安全理由、artifact、cleanup を説明して承認を待つ | 承認前に実行しない |
| Work Unit を完了する | local gate が完了 | gate 結果、未実行 gate、source/hardware 状態、次候補を報告する | `agentic-self-review` を使う |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | 索引から Step 0-8 の依存関係を読み取れる | documentation | 3.1 | `rg` で各仕様名と Step を確認する |
| todo | 各 Work Unit Spec が `振る舞い仕様` と `TDD Test List` を持つ | documentation | 3.1 | Agentic SDD の開始条件 |
| todo | 実機を必要とする項目が `requires_n3dsxl` と承認境界を持つ | safety | 3.1 | hardware gate の抜け漏れ防止 |
| todo | cc3dsfs 由来の値を扱う項目が source audit 要否を持つ | safety | 3.1 | 実装前に原典確認へ戻せる |

### 3.3 設計方針

Work Unit は次の依存順に扱う。

| 順序 | ディレクトリ | 仕様書 | 対応 Step | 実機要否 | Source Audit | 現在状態 |
| ---- | ---------- | ------ | --------- | -------- | ------------ | -------- |
| 0 | `complete/local_009` | `N3DSXL_DEVICE_IDENTITY_AND_SIZES.md` | Step 0 | 不要 | 定数・構造体サイズ | 完了、unit test 通過 |
| 1 | `complete/local_010` | `N3DSXL_DEVICE_DISCOVERY_AND_SESSION.md` | Step 1-2 | listing/open E2E で必要 | identity filter | local 完了、hardware pending |
| 2 | `complete/local_011` | `N3DSXL_FTD3_PIPE_AND_CONNECT.md` | Step 3-4 | command pipe / connect E2E で必要 | command payload / sequence | local 完了、hardware pending |
| 3 | `complete/local_012` | `N3DSXL_RAW_CAPTURE_FIXTURE_AND_DECODER.md` | Step 5-6 | raw capture / PNG 目視で必要 | capture struct / layout | local 完了、raw fixture / manual visual pending |
| 4 | `complete/local_013` | `N3DSXL_ASYNC_STREAMING_ENGINE.md` | Step 7 | streaming E2E で必要 | async transfer sequence | local 完了、hardware pending |
| 5 | `local_014` | `N3DSXL_PERFORMANCE_AND_HARDWARE_GATES.md` | Step 8 | 必要 | 性能値は初回測定で更新 | 未実装 |

Main Agent は上から順に、次を満たす最小単位を選ぶ。

```text
1. 依存 Work Unit の local gate が満たされている。
2. 今回の Intent Delta による優先順位変更がない。
3. 実機 gate が必要な場合、local unit / mock / payload test を先に進められる。
4. source audit が必要な場合、audit item を実装 Work Unit より先に選べる。
5. 選択した Work Unit 以外は実装しない。
```

## 4. 実装仕様

### 4.1 Agentic SDD Bootstrap

Main Agent は、この仕様群を使う作業開始時に次を提示する。

```text
Agentic SDD bootstrap:
- Constitution: AGENTS.md, spec/initial/*, spec/wip/local_008/* ... spec/wip/local_014/*
- Git Context: <branch>, <clean | dirty>, <normal branch | isolated worktree | read-only>
- Intent Delta: none | <summary>
- Selected Work Unit: <spec file + TDD item>
- Dependencies: <met | unmet>
- Non-goals: unselected steps, unsupported devices, GUI, audio playback, recording
- Source Audit: none | required: <item>
- Hardware: not required | approval required: <command scope>
- Gates: <commands and manual gates>
```

### 4.2 Work Unit Selection Pseudocode

```python
def select_next_work_unit(specs: list[WorkUnitSpec], intent_delta: IntentDelta) -> WorkUnit:
    candidates = apply_intent_delta(specs, intent_delta)
    for spec in candidates:
        if not spec.dependencies_met:
            continue
        for item in spec.tdd_items:
            if item.status in {"todo", "red"}:
                return WorkUnit(spec=spec, item=item)
    raise NoLocalWorkUnit("Only hardware-gated or completed work remains")
```

`NoLocalWorkUnit` は completion ではない。実機 gate だけが残っている場合、Main Agent は必要な device identity、command scope、安全理由、artifact、cleanup を説明し、人間承認を待つ。

### 4.3 Non-goals

`local_008` から `local_014` の全仕様で次を非対象にする。

```text
- cc3dsfs GUI
- audio playback
- video encoding / recording
- old DS
- old 3DS の実装
- Optimize / Nisetro / IS Nitro / IS TWL / Partner CTR
- FTD3XX / D2XX vendor driver backend
- GPU acceleration
- streaming 中の 3D mode 切替
```

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| 仕様構成 | 各仕様に template 由来の主要 section がある | `rg -n "## 3. 振る舞い仕様" spec/wip` | 仕様書ごとに hit する |
| Work Unit 分割 | Step 0-8 が対応仕様に出現する | `rg -n "Step [0-8]" spec/wip` | 全 Step が確認できる |
| hardware gate | 実機仕様に marker と承認境界がある | `rg -n "requires_n3dsxl|PONKAN_HARDWARE_APPROVED" spec/wip` | 実機対象仕様に hit する |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| Agentic SDD 開始 | 索引から次候補を選べる | `local_008` から `local_014` が存在する | 完了済み Step 0 を飛ばして Step 1 local task を選べる |
| Source audit 戻り | command 値が未確認 | Step 3 を選ぶ | `cc3dsfs-source-audit` item を先に選べる |
| Hardware 承認待ち | 実機 E2E が必要 | Step 2 以降 | command を実行せず承認待ちにできる |

### 検証コマンド

```console
uv run pytest tests/unit
git diff --check
```

ドキュメント構造確認:

```console
rg -n "Step [0-8]|TDD Test List|requires_n3dsxl|Source Audit" spec/wip
```

## 6. 実装チェックリスト

- [x] `spec/initial` の Step 0-8 を Work Unit 仕様へ分割する。
- [x] 各仕様に振る舞い仕様と TDD Test List を置く。
- [x] source audit 要否を仕様ごとに分ける。
- [x] hardware gate と実機承認境界を仕様ごとに分ける。
- [x] 仕様構成確認を実行する。
- [x] 既存 unit test を実行する。
- [x] レビュー完了。
