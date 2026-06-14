# Capture Profile Roadmap and Source Audit 仕様書

更新日: 2026-06-14

## 1. 概要

### 1.1 目的

N3DSXL 以外の profile を ponkan-python に追加する前提条件を整理し、old 3DS、classic DS、Optimize、Nisetro、IS 系 device の扱いを source audit gate で明確化する。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| roadmap target | 実装済みではないが、将来検討対象として記録する device family。runtime registry には含めない。 |
| source audit | `cc3dsfs` 原典から VID/PID、USB command、構造体サイズ、sequence、layout を抽出し、事実 / 仮説 / 未検証事項を分けて記録する作業。 |
| audit required | source audit 未実施で、runtime profile 追加を開始できない状態。 |
| out of scope | この project の scope 外として明示する状態。 |

### 1.3 背景・問題

`spec/wip/local_027/NYX_CAPTURE_API_HANDOFF.md` の申し送りでは、NyX 連携上は N3DSXL を初期 stable target とし、old 3DS は初期 spec に後続対象として設計枠がある一方、classic DS は現行実装・現行 spec に protocol 詳細が確認できないため別途 source audit が必要と整理されている。Optimize / Nisetro / IS 系 device は docs で非対応が明記されている。

profile registry に未検証 device を安易に追加すると、利用側 UI が「いつか対応するかもしれない device」を誤って通常表示する。この仕様は runtime API ではなく、future profile を追加する前の開発計画と source audit gate として扱う。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| future device | docs と初期 spec から人間が判断 | source audit gate で実装開始可否を判断 |
| old 3DS | 設計枠のみ | audit required として必要 audit を明記 |
| classic DS | protocol 詳細未確認 | audit required のまま runtime registry に出さない |
| out-of-scope device | docs に非対応記載 | runtime registry に追加しない理由を docs に残す |
| scope creep | profile registry 追加が実装扱いになる | source audit / spec / tests / hardware gate を完了条件にする |

### 1.5 着手条件

- [ ] `local_028` の support status 定義がある。
- [ ] `cc3dsfs-source-audit` skill を使う前提で原典調査の記録先を決める。
- [ ] N3DSXL 以外を今回実装しない scope を確認する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_032/CAPTURE_PROFILE_ROADMAP_AND_SOURCE_AUDIT.md` | 新規 | profile roadmap と source audit gate を定義する。 |
| `docs/api.md` | 修正 | N3DSXL 以外の非対象と source audit 前提を明記する。 |
| `spec/wip/local_0xx/*` | 新規 | old3DS / classic DS などを実装する場合の個別 source audit spec。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| N3DSXL を runtime registry に残す | profile list default | `n3dsxl` だけが返る | 現行 target |
| old3DS 実装開始を止める | source audit spec なし | blocked task とする | 実機 command safety |
| classic DS 実装開始を止める | source audit spec なし | blocked task とする | protocol 詳細未確認 |
| out-of-scope device を明示する | Optimize / Nisetro / IS 系 | docs に非対象として残し、runtime registry へ追加しない | 通常 UI には出さない |
| runtime profile へ昇格する | source audit、spec、tests、hardware gate 完了 | 別 Work Unit で `local_028` の registry へ追加する | metadata だけで stable にしない |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | default profile list は N3DSXL 以外を返さない | contract | 3.1 | UI safety |
| todo | old3DS / classic DS 実装開始には source audit spec が必要 | scope guard | 3.1 | 実装なし |
| todo | out-of-scope device は runtime registry に追加しない | scope guard | 3.1 | docs と一致 |
| todo | runtime profile 昇格には gate evidence が必要 | documentation | 3.1 | spec checklist |

### 3.3 設計方針

roadmap は開発計画と source audit gate のために使う。runtime registry や通常 UI には露出しない。

old 3DS は初期 spec に参照領域があるが、実装開始前に source audit spec を別途作成する。classic DS / DS Lite 相当は現行実装・現行 spec で protocol 詳細が確認できないため、source audit なしに registry へ予約しない。

## 4. 実装仕様

roadmap matrix:

| target / family | roadmap state | 根拠 | runtime registry |
| --------------- | ------------- | ---- | ---------------- |
| `n3dsxl` / `new_3ds_xl` | implemented | high-level read / D3XX streaming / performance gate 済み | `local_028` で返す |
| `old3ds` / `o3ds` | audit required | initial spec に後続対象の設計枠あり | 返さない |
| `classic_ds` | audit required | protocol / identity / layout 未確認 | 返さない |
| `optimize` | out of scope | docs で非対象 | 返さない |
| `nisetro` | out of scope | docs で非対象 | 返さない |
| `is_nitro` / `is_twl` / `partner_ctr` | out of scope | docs で非対象 | 返さない |

source audit checklist:

| item | old3DS | classic DS |
| ---- | ------ | ---------- |
| VID/PID | required | required |
| product string / identity boundary | required | required |
| command request values | required | required |
| endpoint / interface | required | required |
| raw capture structure | required | required |
| screen layout / rotation | required | required |
| safe listing without command | required | required |
| first hardware gate plan | required before command | required before command |

runtime profile promotion rule:

```text
audit required -> audited:
  source audit で identity / command / layout の最低限が確認済み。

audited -> experimental:
  implementation exists, unit / characterization tests pass, hardware gate は限定的または未完了。

experimental -> stable:
 実機 E2E、performance / shutdown gate、docs、public API tests が完了。
```

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| profile filtering | default list | include flags なし | N3DSXL 以外は返らない |
| scope guard | old3DS | source audit spec なし | 実装開始を blocked とする |
| scope guard | classic DS | source audit spec なし | 実装開始を blocked とする |
| docs consistency | out-of-scope device | README / docs | runtime registry と矛盾しない |

### 統合テスト

| シナリオ | 検証内容 | 前提条件 | 期待結果 |
| -------- | -------- | -------- | -------- |
| source audit start | old3DS 実装前 | `cc3dsfs-source-audit` | audit spec が先に作られる |
| docs consistency | README / docs / profile metadata | 実機なし | 非対応 device の記述が矛盾しない |

### 検証コマンド

```console
uv run pytest tests/unit/test_capture_profiles.py
uv run ruff format --check .
uv run ruff check .
uv run ty check --no-progress
uv run pytest tests/unit
```

## 6. 実装チェックリスト

- [ ] roadmap matrix を docs に明記する。
- [ ] old3DS / classic DS の audit requirements を docs に明記する。
- [ ] classic DS を source audit 前に通常 profile として返さないことを test する。
- [ ] out-of-scope device family を docs と一致させる。
- [ ] runtime profile promotion rule を docs に追加する。
- [ ] local gate を実行する。
