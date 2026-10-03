<#
.SYNOPSIS
    Local CI: lint + types + tests for backend and frontend.
.EXAMPLE
    powershell -File scripts/check.ps1
    powershell -File scripts/check.ps1 -SkipFrontend
#>
[CmdletBinding()]
param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$failed = New-Object System.Collections.Generic.List[string]

function Invoke-Step {
    param(
        [string]$Name,
        [string]$WorkDir,
        [scriptblock]$Command
    )
    Write-Host "==> $Name" -ForegroundColor Cyan
    Push-Location $WorkDir
    try {
        & $Command
        if ($LASTEXITCODE -ne 0) {
            $failed.Add($Name)
        }
    }
    finally {
        Pop-Location
    }
}

if (-not $SkipBackend) {
    $backend = Join-Path $root 'backend'
    Invoke-Step 'backend: ruff check' $backend { uv run ruff check . }
    Invoke-Step 'backend: ruff format' $backend {
        uv run ruff format --check .
    }
    Invoke-Step 'backend: mypy' $backend { uv run mypy }
    Invoke-Step 'backend: pytest' $backend { uv run pytest -q }
}

if (-not $SkipFrontend) {
    $frontend = Join-Path $root 'frontend'
    Invoke-Step 'frontend: tsc' $frontend { npm run typecheck }
    Invoke-Step 'frontend: eslint' $frontend { npm run lint }
    Invoke-Step 'frontend: prettier' $frontend { npm run format:check }
    Invoke-Step 'frontend: vitest' $frontend { npm run test }
}

if ($failed.Count -gt 0) {
    Write-Host "FAILED steps:" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}
Write-Host "All checks passed." -ForegroundColor Green
