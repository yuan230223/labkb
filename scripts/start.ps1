param([int]$Port = 8765)

$ErrorActionPreference = 'Stop'
$labRoot = Split-Path -Parent $PSScriptRoot
$labPython = Join-Path $labRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $labPython)) {
    throw 'Create .venv and install the project first; see README.md.'
}
Set-Location -LiteralPath $labRoot
& $labPython -m labkb --port $Port
