# Dev Journal

実装中の設計上の気づき・疑問・バックログ送りタスクの記録。

## 2026-06-15: D3XX discovery failure の result object 化

### 現状

`list_capture_devices()` は PyD3XX import failure などの `DependencyUnavailableError` を `CaptureDeviceDiscovery(backend_status="unavailable")` に変換する。一方、D3XX native API call failure や descriptor detail の unsupported shape は `D3xxBackendError` として送出される。

### 観察

discovery API を「接続候補と backend 状態を返す診断 API」と見るなら、D3XX API failure も result object に畳む設計が考えられる。ただし、例外を result に変換すると throw / no-throw 境界が変わり、technical log 用の `function` / `status` / `field_name` をどこへ保持するかも再設計が必要になる。

### 方針

今回の `local_033` 仕様では、`D3xxBackendError` の structured fields と root export の整理を優先し、D3XX discovery failure の result object 化は先送りする。将来扱う場合は `CaptureDeviceDiscovery` に backend-specific detail を持たせるか、`D3xxBackendError` をそのまま送出する現在の contract を維持するかを先に決める。
