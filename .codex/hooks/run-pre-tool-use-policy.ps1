$ErrorActionPreference = "Stop"

$repoRoot = git rev-parse --show-toplevel
$scriptPath = Join-Path $repoRoot ".codex/hooks/pre_tool_use_policy.py"
$payload = [Console]::In.ReadToEnd()

Set-Location -LiteralPath $repoRoot
$env:UV_CACHE_DIR = Join-Path $repoRoot ".uv-cache"
$payload | uv run python $scriptPath
exit $LASTEXITCODE
