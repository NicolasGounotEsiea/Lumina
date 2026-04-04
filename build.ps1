$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$appName = "LuminaControl"
$iconPng = Join-Path $root "icon.png"
$iconIco = Join-Path $root "icon.ico"

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Ensure-Icon {
    if (Test-Path $iconIco) { return }

    if (Test-Command "magick") {
        Write-Host "Generating icon.ico via ImageMagick..."
        & magick $iconPng -define icon:auto-resize=256,128,64,48,32,16 $iconIco
        if (Test-Path $iconIco) { return }
    }

    Write-Host "icon.ico not found. Please create a multi-size .ico (16/32/48/256) and place it at:`n$iconIco" -ForegroundColor Yellow
    exit 1
}

function Find-ISCC {
    $cmd = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    return $null
}

Ensure-Icon

Write-Host "Cleaning old build outputs..."
Remove-Item -Recurse -Force (Join-Path $root "build") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $root "dist") -ErrorAction SilentlyContinue
Remove-Item -Force (Join-Path $root "$appName.spec") -ErrorAction SilentlyContinue

Write-Host "Building EXE with PyInstaller..."
& pyinstaller --noconsole --name $appName --icon $iconIco `
  --add-data "icon.png;." `
  multiscreen_tray.py

$iscc = Find-ISCC
if (-not $iscc) {
    Write-Host "ISCC.exe not found. Install Inno Setup or add it to PATH." -ForegroundColor Yellow
    exit 1
}

Write-Host "Building installer..."
& $iscc "installer.iss"

Write-Host "Done. Installer is in dist-installer\${appName}Setup.exe"
