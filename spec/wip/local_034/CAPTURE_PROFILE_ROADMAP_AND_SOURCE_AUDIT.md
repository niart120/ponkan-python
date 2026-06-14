# Capture Profile Roadmap and Source Audit 仕様書

更新日: 2026-06-14

## 1. 概要

### 1.1 目的

N3DSXL 以外の profile を ponkan-python に追加する前提条件を整理し、old 3DS、classic DS、Optimize、Nisetro、IS 系 device の扱いを support status と source audit gate で明確化する。

### 1.2 用語定義

| 用語 | 定義 |
| ---- | ---- |
| roadmap profile | 実装済みではないが、将来検討対象として status を管理する profile。 |
| source audit | `cc3dsfs` 原典から VID/PID、USB command、構造体サイズ、sequence、layout を抽出し、事実 / 仮説 / 未検証事項を分けて記録する作業。 |
| planned | 設計枠はあるが実装・実機 gate 未完了の status。 |
| unknown | source audit 未実施で、support 可否も判断しない status。 |
| unsupported | この project の scope 外として明示する status。 |

### 1.3 背景・問題

tmp の申し送りでは、NyX 連携上は N3DSXL を初期 stable target とし、old 3DS は初期 spec に後続対象として設計枠がある一方、classic DS は現行実装・現行 spec に protocol 詳細が確認できないため別途 source audit が必要と整理されている。Optimize / Nisetro / IS 系 device は docs で非対応が明記されている。

profile registry に未検証 device を安易に追加すると、利用側 UI が「いつか対応するかもしれない device」を誤って通常表示する。roadmap は通常 UI 用ではなく、diagnostics と開発計画用の contract として扱う。

### 1.4 期待効果

| 指標 | 現状 | 目標 |
| ---- | ---- | ---- |
| future device | docs と初期 spec から人間が判断 | support status と source audit gate で判断 |
| old 3DS | 設計枠のみ | `planned` として必要 audit を明記 |
| classic DS | protocol 詳細未確認 | `unknown` のまま通常 registry に出さない |
| unsupported device | docs に非対応記載 | `unsupported` reason を diagnostics に出せる |
| scope creep | profile registry 追加が実装扱いになる | source audit / spec / tests / hardware gate を完了条件にする |

### 1.5 着手条件

- [ ] `local_027` の support status 定義がある。
- [ ] `cc3dsfs-source-audit` skill を使う前提で原典調査の記録先を決める。
- [ ] N3DSXL 以外を今回実装しない scope を確認する。

## 2. 対象ファイル

| ファイル | 変更種別 | 変更内容 |
| -------- | -------- | -------- |
| `spec/wip/local_034/CAPTURE_PROFILE_ROADMAP_AND_SOURCE_AUDIT.md` | 新規 | profile roadmap と source audit gate を定義する。 |
| `src/ponkan/profiles.py` | 修正 | diagnostics mode で planned / unsupported / unknown を表現する場合の metadata を追加する。 |
| `docs/api.md` | 修正 | N3DSXL 以外の support status と非対象を明記する。 |
| `spec/wip/local_0xx/*` | 新規 | old3DS / classic DS などを実装する場合の個別 source audit spec。 |
| `tests/unit/test_capture_profiles.py` | 修正 | roadmap status が通常 UI filtering に混ざらないことを検証する。 |

## 3. 振る舞い仕様と設計方針

### 3.1 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
| -------- | ---------- | -------- | ---- |
| N3DSXL を通常表示する | profile list default | `n3dsxl` が stable / experimental として返る | 現行 target |
| old3DS を diagnostics 表示する | include planned / diagnostics | `planned` と source audit requirements を返す | 実装なし |
| classic DS を通常非表示にする | default profile list | 返さない | source audit 未実施 |
| unsupported を明示する | diagnostics mode | Optimize / Nisetro / IS 系を `unsupported` reason 付きで返す | 通常 UI には出さない |
| source audit 前の実装を防ぐ | old3DS / classic DS 実装開始 | audit checklist 未完了なら blocked task とする | 実機 command safety |
| support status を上げる | planned -> experimental / stable | spec、tests、hardware gate を満たす | metadata だけで stable にしない |

### 3.2 TDD Test List

| 状態 | テスト項目 | 種別 | 関連仕様 | 備考 |
| ---- | ---------- | ---- | -------- | ---- |
| todo | default profile list は unsupported / unknown を返さない | contract | 3.1 | UI safety |
| todo | diagnostics mode は unsupported reason を返す | diagnostics | 3.1 | docs と一致 |
| todo | old3DS planned metadata に audit requirements が含まれる | planning | 3.1 | 実装なし |
| todo | classic DS は source audit 前に planned 扱いしない | scope guard | 3.1 | unknown / omitted |
| todo | support status promotion には gate evidence が必要 | documentation | 3.1 | spec checklist |

### 3.3 設計方針

roadmap metadata は開発計画と diagnostics のために使う。通常 UI は `stable` / `experimental` のみを表示し、`planned` / `unsupported` / `unknown` は隠す。

old 3DS は初期 spec に参照領域があるため `planned` にできるが、実装開始前に source audit spec を別途作成する。classic DS / DS Lite 相当は現行実装・現行 spec で protocol 詳細が確認できないため、source audit なしに registry へ予約しない。

## 4. 実装仕様

support matrix:

| profile / family | status | 根拠 | 通常 UI |
| ---------------- | ------ | ---- | ------- |
| `n3dsxl` / `new_3ds_xl` | `stable` | high-level read / D3XX streaming / performance gate 済み | 表示 |
| `old3ds` / `o3ds` | `planned` | initial spec に後続対象の設計枠あり | 非表示 |
| `classic_ds` | `unknown` または未登録 | protocol / identity / layout 未確認 | 非表示 |
| `optimize` | `unsupported` | docs で非対象 | 非表示 |
| `nisetro` | `unsupported` | docs で非対象 | 非表示 |
| `is_nitro` / `is_twl` / `partner_ctr` | `unsupported` | docs で非対象 | 非表示 |

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

promotion rule:

```text
unknown -> planned:
  source audit で identity / command / layout の最低限が確認済み。

planned -> experimental:
  implementation exists, unit / characterization tests pass, hardware gate は限定的または未完了。

experimental -> stable:
 実機 E2E、performance / shutdown gate、docs、public API tests が完了。
```

## 5. テスト方針

### ユニットテスト

| テスト対象 | 検証内容 | 入力例 | 期待結果 |
| ---------- | -------- | ------ | -------- |
| profile filtering | default list | include flags なし | stable / experimental / planned policy 通り |
| diagnostics | unsupported reason | include_unsupported | reason が返る |
| roadmap metadata | old3DS | diagnostics | planned と audit requirements |
| scope guard | classic DS | default | 返らない |

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

- [ ] support matrix を `profiles.py` diagnostics metadata に反映するか決める。
- [ ] old3DS planned status と audit requirements を docs に明記する。
- [ ] classic DS を source audit 前に通常 profile として返さないことを test する。
- [ ] unsupported device family の reason を docs と一致させる。
- [ ] support status promotion rule を docs に追加する。
- [ ] local gate を実行する。
