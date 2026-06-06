$ErrorActionPreference = "Stop"

$repoRoot = git rev-parse --show-toplevel
$scriptPath = Join-Path $repoRoot ".codex/hooks/pre_tool_use_policy.py"
$payload = [Console]::In.ReadToEnd()

$payload | uv run python $scriptPath
exit $LASTEXITCODE
