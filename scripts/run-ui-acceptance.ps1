$ErrorActionPreference = 'Stop'

$project = Split-Path -Parent $PSScriptRoot
Set-Location $project
$python = Join-Path $project '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment Python was not found at $python"
}

Write-Host 'Running Bible Brain UI and database acceptance tests…'
& $python -m unittest discover -s tests -q
if ($LASTEXITCODE -ne 0) {
    throw "Acceptance tests failed with exit code $LASTEXITCODE"
}

$portable = Join-Path $project 'dist\Bible Brain\Bible Brain.exe'
$installer = Join-Path $project 'dist\Bible-Brain-Setup-0.2.0-x64-user.msi'
foreach ($artifact in @($portable, $installer)) {
    if (-not (Test-Path -LiteralPath $artifact)) {
        throw "Expected release artifact is missing: $artifact"
    }
}

Write-Host 'Acceptance tests passed.'
Write-Host "Portable: $portable"
Write-Host "Per-user installer: $installer"
