$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$python = Join-Path $project '.venv\Scripts\python.exe'
$previousPyInstallerCache = $env:PYINSTALLER_CONFIG_DIR
$scratchRoot = (Resolve-Path -LiteralPath ([IO.Path]::GetTempPath())).Path
$buildId = [guid]::NewGuid().ToString('N')
$scratch = Join-Path $scratchRoot ('bible-brain-build-' + $buildId)
New-Item -ItemType Directory -Path $scratch | Out-Null

function Remove-BuildDirectory([string] $Path, [string] $Parent) {
    $resolved = Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue
    if ($resolved -and (Split-Path -Parent $resolved.Path) -eq $Parent.TrimEnd('\')) {
        Remove-Item -LiteralPath $resolved.Path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Push-Location -LiteralPath $project
try {
    $staged = Join-Path $scratch 'dist'
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $scratch 'cache'
    & $python -m PyInstaller --noconfirm --workpath (Join-Path $scratch 'work') --distpath $staged BibleBrain.spec
    if ($LASTEXITCODE -ne 0) { throw 'The Windows build failed.' }

    # Publish only after staging has completed. Windows sync tools can hold old build files open.
    $distFolder = (New-Item -ItemType Directory -Path (Join-Path $project 'dist') -Force).FullName
    $dist = (Resolve-Path -LiteralPath $distFolder).Path
    if ((Split-Path -Parent $dist) -ne (Resolve-Path -LiteralPath $project).Path) {
        throw 'The distribution directory is outside the Bible Brain project.'
    }
    $built = Join-Path $dist 'Bible Brain'
    $incoming = Join-Path $dist ('.Bible Brain.incoming-' + $buildId)
    $previousName = '.Bible Brain.previous-' + $buildId
    $previous = Join-Path $dist $previousName
    Copy-Item -LiteralPath (Join-Path $staged 'Bible Brain') -Destination $incoming -Recurse
    if (Test-Path -LiteralPath $built) {
        $resolvedBuilt = (Resolve-Path -LiteralPath $built).Path
        if ((Split-Path -Parent $resolvedBuilt) -ne $dist) { throw 'Unexpected build folder location.' }
        Rename-Item -LiteralPath $resolvedBuilt -NewName $previousName
    }
    try {
        Rename-Item -LiteralPath $incoming -NewName 'Bible Brain'
    } catch {
        if (Test-Path -LiteralPath $previous) { Rename-Item -LiteralPath $previous -NewName 'Bible Brain' }
        throw
    }
    Remove-BuildDirectory $previous $dist
    Write-Output (Join-Path $built 'Bible Brain.exe')
} finally {
    $env:PYINSTALLER_CONFIG_DIR = $previousPyInstallerCache
    Pop-Location
    Remove-BuildDirectory $scratch $scratchRoot
}
