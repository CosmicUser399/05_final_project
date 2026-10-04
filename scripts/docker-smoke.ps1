<#
.SYNOPSIS
    Docker deployment smoke test (T070 / P12-04).
.DESCRIPTION
    Starts compose (if needed), waits for nginx:18080 health/ready,
    checks API through the reverse proxy, then optionally tears down.
.EXAMPLE
    powershell -File scripts/docker-smoke.ps1
    powershell -File scripts/docker-smoke.ps1 -SkipUp
#>
[CmdletBinding()]
param(
    [switch]$SkipUp,
    [switch]$KeepUp,
    [int]$TimeoutSeconds = 180,
    [string]$BaseUrl = 'http://localhost:18080'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Wait-HttpOk {
    param(
        [string]$Url,
        [int]$TimeoutSec
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                return $response
            }
        }
        catch {
            Start-Sleep -Seconds 3
        }
    }
    throw "Timeout waiting for $Url"
}

Push-Location $root
try {
    if (-not $SkipUp) {
        Write-Host '==> docker compose up --build -d' -ForegroundColor Cyan
        docker compose up --build -d
        if ($LASTEXITCODE -ne 0) {
            throw 'docker compose up failed'
        }
    }

    Write-Host "==> wait $BaseUrl/health" -ForegroundColor Cyan
    $health = Wait-HttpOk -Url "$BaseUrl/health" -TimeoutSec $TimeoutSeconds
    $healthJson = $health.Content | ConvertFrom-Json
    if ($healthJson.status -ne 'ok') {
        throw "health status is $($healthJson.status)"
    }

    Write-Host "==> wait $BaseUrl/ready" -ForegroundColor Cyan
    $ready = Wait-HttpOk -Url "$BaseUrl/ready" -TimeoutSec $TimeoutSeconds
    $readyJson = $ready.Content | ConvertFrom-Json
    if ($readyJson.status -ne 'ok' -and $readyJson.status -ne 'ready') {
        # Accept either convention used by the app.
        Write-Host "ready payload: $($ready.Content)"
    }

    Write-Host "==> GET $BaseUrl/api/v1/systems" -ForegroundColor Cyan
    $systems = Invoke-WebRequest -Uri "$BaseUrl/api/v1/systems" -UseBasicParsing
    if ($systems.StatusCode -ne 200) {
        throw "systems endpoint returned $($systems.StatusCode)"
    }

    Write-Host "==> GET $BaseUrl/ (frontend)" -ForegroundColor Cyan
    $front = Invoke-WebRequest -Uri "$BaseUrl/" -UseBasicParsing
    if ($front.StatusCode -ne 200) {
        throw "frontend returned $($front.StatusCode)"
    }

    Write-Host 'Docker smoke passed.' -ForegroundColor Green
}
finally {
    if (-not $KeepUp -and -not $SkipUp) {
        Write-Host '==> docker compose down' -ForegroundColor Cyan
        docker compose down
    }
    Pop-Location
}
