[CmdletBinding()]
param(
    [ValidatePattern('^\d{1,3}\.\d{1,3}\.\d{1,5}$')]
    [string] $Version,
    [string] $BuildDirectory,
    [string] $OutputDirectory,
    [switch] $PerUser
)

$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
if (-not $Version) {
    $versionSource = Get-Content -LiteralPath (Join-Path $project 'bible_brain\__init__.py') -Raw
    $match = [regex]::Match($versionSource, '(?m)^__version__\s*=\s*"(?<version>\d{1,3}\.\d{1,3}\.\d{1,5})"')
    if (-not $match.Success) { throw 'Could not read the numeric application version. Pass -Version explicitly.' }
    $Version = $match.Groups['version'].Value
}
if (-not $BuildDirectory) { $BuildDirectory = Join-Path $project 'dist\Bible Brain' }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $project 'dist' }

$application = (Resolve-Path -LiteralPath $BuildDirectory).Path
$executable = Join-Path $application 'Bible Brain.exe'
$internal = Join-Path $application '_internal'
if (-not (Test-Path -LiteralPath $executable -PathType Leaf) -or
    -not (Test-Path -LiteralPath $internal -PathType Container)) {
    throw 'Expected the executable and _internal folder from scripts/build-windows.ps1.'
}

$applicationVersion = [version] $Version
if ($applicationVersion.Major -gt 255 -or $applicationVersion.Minor -gt 255 -or $applicationVersion.Build -gt 65535) {
    throw 'Windows Installer versions have the range 0.0.0 through 255.255.65535.'
}
$Version = $applicationVersion.ToString(3)
$packageSuffix = ''
$scopeArguments = @()
if ($PerUser) {
    $packageSuffix = '-user'
    $scopeArguments = @('-dPerUser=1')
}
# A rebuild of the same release should have the same Windows Installer product identity.
$sha = [Security.Cryptography.SHA256]::Create()
try {
    $digest = $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes("Bible Brain x64 MSI $Version$packageSuffix"))
} finally {
    $sha.Dispose()
}
$digest[7] = ($digest[7] -band 15) -bor 128
$digest[8] = ($digest[8] -band 63) -bor 128
$productCode = [guid]::new([byte[]] $digest[0..15]).ToString()

$reader = [IO.BinaryReader]::new([IO.File]::OpenRead($executable))
try {
    $reader.BaseStream.Position = 0x3c
    $reader.BaseStream.Position = $reader.ReadUInt32()
    if ($reader.ReadUInt32() -ne 0x4550 -or $reader.ReadUInt16() -ne 0x8664) {
        throw 'The MSI packages the Windows x64 executable. Build the application with x64 Python.'
    }
} finally {
    $reader.Dispose()
}

$tools = Join-Path $project '.build-tools'
$wix = Join-Path $tools 'wix-3.14.1'
$commands = @('heat.exe', 'candle.exe', 'light.exe')
$missingCommand = $commands | Where-Object { -not (Test-Path -LiteralPath (Join-Path $wix $_) -PathType Leaf) }
if ($missingCommand) {
    New-Item -ItemType Directory -Path $tools -Force | Out-Null
    $archive = Join-Path $tools 'wix314-binaries.zip'
    $url = 'https://github.com/wixtoolset/wix3/releases/download/wix3141rtm/wix314-binaries.zip'
    $sha256 = '6AC824E1642D6F7277D0ED7EA09411A508F6116BA6FAE0AA5F2C7DAA2FF43D31'
    if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $url -OutFile $archive
    }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $sha256) {
        throw "WiX archive checksum mismatch. Remove '$archive' to download it again."
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $wix -Force
}

$intermediate = Join-Path $tools "installer$packageSuffix"
New-Item -ItemType Directory -Path $intermediate, $OutputDirectory -Force | Out-Null
$output = (Resolve-Path -LiteralPath $OutputDirectory).Path
$harvest = Join-Path $intermediate 'Application.wxs'
$source = Join-Path $project 'installer\BibleBrain.wxs'
$msi = Join-Path $output "Bible-Brain-Setup-$Version-x64$packageSuffix.msi"

& (Join-Path $wix 'heat.exe') dir $internal -nologo -ag -scom -sreg -sfrag -srd `
    -dr INTERNALFOLDER -cg BibleBrainFiles -var var.InternalSource -out $harvest
if ($LASTEXITCODE -ne 0) { throw 'WiX could not harvest the application bundle.' }

& (Join-Path $wix 'candle.exe') -nologo -arch x64 "-dAppSource=$application" "-dInternalSource=$internal" `
    "-dAppVersion=$Version" "-dProductCode=$productCode" @scopeArguments -out "$intermediate\" $source $harvest
if ($LASTEXITCODE -ne 0) { throw 'WiX could not compile the installer definition.' }

& (Join-Path $wix 'light.exe') -nologo -ext WixUIExtension -spdb -out $msi `
    (Join-Path $intermediate 'BibleBrain.wixobj') (Join-Path $intermediate 'Application.wixobj')
if ($LASTEXITCODE -ne 0) { throw 'WiX could not link and validate the installer.' }

Write-Output $msi
