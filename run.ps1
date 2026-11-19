param(
    [int]$Port = 4317,
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot '.venv'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython)) {
    python -m venv $venvPath
}

if (-not $SkipInstall) {
    & $venvPython -m pip install --disable-pip-version-check -r (Join-Path $projectRoot 'requirements.txt')
}

Set-Location -LiteralPath $projectRoot
& $venvPython -m uvicorn backend.server:app --host 127.0.0.1 --port $Port
