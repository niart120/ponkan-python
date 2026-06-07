---
name: n3dsxl-hardware-harness
description: "new 3DS XL capture board を使う実機検証の安全手順、pytest marker、driver/USB 状態、raw artifact 保存を確認するスキル。USE WHEN: requires_n3dsxl テスト、probe、raw capture、streaming smoke test を実行・設計するとき。"
---

# N3DSXL Hardware Harness

実機 new 3DS XL capture board を使うテストや probe を行う前に、安全条件と記録項目を確認する。

## 実行前チェック

- 対象 device の VID が `0x0403` であること。
- PID が `0x601e`, `0x601f`, `0x602a`, `0x602b`, `0x602c`, `0x602d`, `0x602f` のいずれかであること。
- product string が読める場合、`N3DSXL` または `N3DSXL.2` であること。
- product string が読めない場合、`product_string_status=unreadable` を記録し、許可済み VID/PID と人間の明示承認を safety boundary として扱うこと。
- 実機テストに `@pytest.mark.requires_n3dsxl` が付いていること。
- performance test に `@pytest.mark.performance` が付いていること。
- CI では実機テストを実行しないこと。

## 実行時ルール

- raw frame 取得に成功したら `.bin` と `.json` metadata を保存する。
- metadata には product string、product string status、VID/PID、mode_3d、transferred、video_size、capture_size を含める。
- 失敗時は command 名、libusb status、transferred bytes、cleanup 結果を記録する。
- stop / 例外時は pending transfer cancel、drain、interface release、handle close を確認する。

## Windows driver 切り分け

- listing が成功して open が `LIBUSB_ERROR_NOT_FOUND` で失敗する場合、PnP service を確認する。
- `FTDIBUS3` が bound されている場合、FTDI D3XX driver では見えているが libusb open path では開けない可能性がある。
- この状態では product string policy の問題と driver/backend 問題を分けて報告する。

## ローカル実行

```console
$env:PONKAN_RUN_N3DSXL = "1"
uv run pytest -m requires_n3dsxl tests/e2e

$env:PONKAN_RUN_PERFORMANCE = "1"
uv run pytest -m "requires_n3dsxl and performance" tests/performance
```

## 禁止事項

- product string が読めて `N3DSXL` / `N3DSXL.2` でない device に command を送らない。
- VID/PID が許可範囲外の device に command を送らない。
- callback 内で decode、Pillow 変換、blocking queue put を行わない。
- unbounded queue を streaming 経路に入れない。
