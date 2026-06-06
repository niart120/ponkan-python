---
name: cc3dsfs-source-audit
description: "cc3dsfs 原典 C++ から ponkan-python に必要な定数・USB command・構造体サイズ・sequence を抽出し、参照元と検証状態を記録するスキル。USE WHEN: cc3dsfs の source/include を読み、Python 実装へ反映する調査や characterization を行うとき。"
---

# cc3dsfs Source Audit

`cc3dsfs` の C++ 実装を参照し、ponkan-python に必要な事実と仮説を分けて記録する。

## 対象

- `source/CaptureDeviceSpecific/3DSCapture_FTD3/`
- `include/CaptureDeviceSpecific/3DSCapture_FTD3/`
- `include/capture_structs.hpp`
- `include/hw_defs.hpp`
- old 3DS 調査時は `usb_ds_3ds_capture.*`

## 記録ルール

- 抽出した値には参照元 path または URL を付ける。
- 事実、推定、未検証仮説を分ける。
- 実機で確認した値は日時、OS、product string、VID/PID と一緒に記録する。
- command payload を変更する場合は、差分理由と原典上の根拠を記録する。

## 禁止事項

- 未知 VID/PID/product string の device に N3DSXL command を送らない。
- 参照元が不明な magic number を確定値として実装しない。
- GUI、audio、非 N3DSXL device の実装を Step 外で広げない。

## 出力先

- 作業仕様: `spec/wip/local_{連番}/FEATURE_NAME.md`
- 小さな観測: `spec/dev-journal.md`
- テスト固定値: `tests/unit/`
