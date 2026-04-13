param(
    [switch]$InstallBuildTool,
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot

Set-Location $RepoRoot

Write-Host 'Building CT-CatPhan executable...'

if ($InstallBuildTool) {
    Write-Host 'Installing PyInstaller into the current environment...'
    python -m pip install pyinstaller
}

Write-Host 'Refreshing editable package install...'
python -m pip install -e .

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
}
else {
    python -m PyInstaller packaging/pyinstaller/CT-CatPhan.spec
}

Write-Host ''
Write-Host 'Build complete.'
Write-Host 'Executable: dist/CT-CatPhan.exe'