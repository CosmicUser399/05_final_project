<#
.SYNOPSIS
    Developer helper: setup, run backend/frontend, compose up/down.
.EXAMPLE
    powershell -File scripts/dev.ps1 setup
    powershell -File scripts/dev.ps1 backend
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'backend', 'frontend', 'up', 'down', 'init-db')]
    [string]$Task = 'setup'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Initialize-Database {
    $dataDir = Join-Path $root 'data'
    New-Item -ItemType Directory -Force $dataDir | Out-Null
    $db = Join-Path $dataDir 'app.db'
    if (-not (Test-Path $db)) {
        New-Item -ItemType File $db | Out-Null
        Write-Host "Created empty $db"
    }
    Push-Location (Join-Path $root 'backend')
    try {
        uv run alembic upgrade head
        Write-Host 'Applied Alembic migrations'
    }
    finally { Pop-Location }
}

switch ($Task) {
    'init-db' { Initialize-Database }
    'setup' {
        Initialize-Database
        Push-Location (Join-Path $root 'backend'); uv sync; Pop-Location
        Push-Location (Join-Path $root 'frontend'); npm ci; Pop-Location
        if (-not (Test-Path (Join-Path $root '.env'))) {
            Copy-Item (Join-Path $root '.env.example') (Join-Path $root '.env')
            Write-Host 'Created .env from .env.example'
        }
    }
    'backend' {
        Initialize-Database
        Push-Location (Join-Path $root 'backend')
        try {
            uv run uvicorn app.main:app --reload --port 8000
        }
        finally { Pop-Location }
    }
    'frontend' {
        Push-Location (Join-Path $root 'frontend')
        try { npm run dev } finally { Pop-Location }
    }
    'up' { docker compose -f (Join-Path $root 'docker-compose.yml') up --build -d }
    'down' { docker compose -f (Join-Path $root 'docker-compose.yml') down }
}
