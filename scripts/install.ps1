# Install a released Loop executable into a user-owned directory.
param(
    [string]$Version = '',
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\Loop\bin'),
    [string]$Repository = 'domhauton/loop-cli-adk',
    [string]$Archive = '',
    [string]$Checksums = ''
)
$ErrorActionPreference = 'Stop'
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
$stageDir = ''
New-Item -ItemType Directory -Path $tempDir | Out-Null
try {
    if (-not $Archive) {
        if ($Repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') { throw 'Invalid repository' }
        if (-not $Version) {
            $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repository/releases/latest"
            $Version = $release.tag_name
        }
        $Version = $Version -replace '^v', ''
        if ($Version -notmatch '^0\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$') { throw 'Expected a released v0 semantic version' }
        $arch = switch ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()) {
            'X64' { 'amd64' }
            'Arm64' { 'arm64' }
            default { throw 'Unsupported architecture' }
        }
        $Archive = Join-Path $tempDir "loop_${Version}_windows_${arch}.zip"
        $Checksums = Join-Path $tempDir 'checksums.txt'
        $baseUrl = "https://github.com/$Repository/releases/download/v$Version"
        Invoke-WebRequest -Uri "$baseUrl/$([System.IO.Path]::GetFileName($Archive))" -OutFile $Archive
        Invoke-WebRequest -Uri "$baseUrl/checksums.txt" -OutFile $Checksums
    }
    if (-not $Checksums) { throw 'A checksum file is required' }
    $filename = [System.IO.Path]::GetFileName($Archive)
    $pattern = '^([a-fA-F0-9]{64})\s+' + [regex]::Escape($filename) + '$'
    $matchesFound = @(Get-Content $Checksums | Select-String -Pattern $pattern)
    if ($matchesFound.Count -ne 1) { throw 'Missing or ambiguous archive checksum' }
    $expected = $matchesFound[0].Matches[0].Groups[1].Value
    if ((Get-FileHash $Archive -Algorithm SHA256).Hash -ne $expected) { throw 'Archive checksum mismatch' }
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    $stageDir = Join-Path $InstallDir ('.loop-install-' + [guid]::NewGuid().ToString())
    New-Item -ItemType Directory -Path $stageDir | Out-Null
    # Extract only the executable, never paths supplied by arbitrary ZIP entries.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path $Archive))
    try {
        $entry = $zip.GetEntry('loop.exe')
        if (-not $entry) { throw 'Archive must contain loop.exe' }
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, (Join-Path $stageDir 'loop.exe'))
    } finally { $zip.Dispose() }
    Move-Item -Path (Join-Path $stageDir 'loop.exe') -Destination (Join-Path $InstallDir 'loop.exe') -Force
    Write-Output "Installed Loop to $InstallDir\loop.exe"
    Write-Output "If needed, add $InstallDir to your user PATH. Remove that executable to uninstall."
} finally {
    Remove-Item -Path $tempDir -Recurse -Force
    if ($stageDir -and (Test-Path $stageDir)) { Remove-Item -Path $stageDir -Recurse -Force }
}
