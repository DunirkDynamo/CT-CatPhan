param(
    [switch]$InstallBuildTool,
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Assert-LastExitCode {
    param(
        [string]$Context
    )

    if ($LASTEXITCODE -ne 0) {
        throw "$Context failed with exit code $LASTEXITCODE"
    }
}

Set-Location $RepoRoot

Write-Host 'Building CT-CatPhan executable...'

if ($InstallBuildTool) {
    Write-Host 'Installing PyInstaller into the current environment...'
    python -m pip install pyinstaller
    Assert-LastExitCode 'PyInstaller installation'
}

Write-Host 'Refreshing editable package install...'
python -m pip install -e .
Assert-LastExitCode 'Editable package installation'

if ($Clean) {
    Write-Host 'Removing previous build artifacts...'
    if (Test-Path 'build') {
        Remove-Item 'build' -Recurse -Force
    }
    if (Test-Path 'dist') {
        Remove-Item 'dist' -Recurse -Force
    }
}

Write-Host 'Running PyInstaller...'
if ($Clean) {
    python -m PyInstaller --clean packaging/pyinstaller/CT-CatPhan.spec
    Assert-LastExitCode 'PyInstaller clean build'
}
else {
    python -m PyInstaller packaging/pyinstaller/CT-CatPhan.spec
    Assert-LastExitCode 'PyInstaller build'
}

Write-Host ''
Write-Host 'Build complete.'
Write-Host 'Executable: dist/CT-CatPhan.exe'