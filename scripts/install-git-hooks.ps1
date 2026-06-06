$ErrorActionPreference = "Stop"

function Invoke-Native {
    & $args[0] @($args | Select-Object -Skip 1)
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $($args -join ' ')"
    }
}

$repoRoot = git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0) {
    throw "Failed to resolve git repository root."
}

Set-Location $repoRoot

Invoke-Native git config core.hooksPath .githooks

$hooksPath = git config --get core.hooksPath
if ($LASTEXITCODE -ne 0) {
    throw "Failed to read core.hooksPath."
}

Write-Host "Configured core.hooksPath=$hooksPath"
