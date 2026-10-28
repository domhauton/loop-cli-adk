$ErrorActionPreference = 'Stop'
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $tempDir | Out-Null
try {
    $env:CGO_ENABLED = '0'
    go build -o (Join-Path $tempDir 'loop.exe') ./cmd/loop
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
    $archive = Join-Path $tempDir 'fixture.zip'
    Compress-Archive -Path (Join-Path $tempDir 'loop.exe') -DestinationPath $archive
    $checksum = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    $checksums = Join-Path $tempDir 'checksums.txt'
    "$checksum  fixture.zip" | Set-Content $checksums
    $installDir = Join-Path $tempDir 'install with spaces'
    & ./scripts/install.ps1 -Archive $archive -Checksums $checksums -InstallDir $installDir
    $version = & (Join-Path $installDir 'loop.exe') version
    if ($LASTEXITCODE -ne 0 -or $version -ne 'dev') { throw 'Installed executable failed' }
    Add-Content -Path $archive -Value 'damaged'
    $rejected = $false
    try { & ./scripts/install.ps1 -Archive $archive -Checksums $checksums -InstallDir $installDir } catch { $rejected = $true }
    if (-not $rejected) { throw 'Installer accepted a damaged archive' }
    $version = & (Join-Path $installDir 'loop.exe') version
    if ($LASTEXITCODE -ne 0 -or $version -ne 'dev') { throw 'Failed upgrade damaged existing installation' }
} finally { Remove-Item -Path $tempDir -Recurse -Force }
