# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Lumina Control** is a Windows desktop system tray application for controlling multi-monitor brightness, contrast, and color calibration via DDC-CI protocol. The entire application lives in a single file: `multiscreen_tray.py`.

## Commands

**Run the application:**
```bash
python multiscreen_tray.py
```

**Build standalone executable + installer:**
```powershell
.\build.ps1
```
This requires ImageMagick (icon generation), PyInstaller, and Inno Setup 6 (`C:\Program Files (x86)\Inno Setup 6\ISCC.exe`). Output: `dist-installer\LuminaControlSetup.exe`.

**Install dependencies** (no `requirements.txt` — infer from `.venv`):
```bash
pip install PySide6 monitorcontrol screeninfo pywin32
```

## Architecture

The entire application is ~1850 lines in `multiscreen_tray.py`. Key classes:

- **`MainWindow(QWidget)`** — Main floating window. Manages all monitors, sync logic, gamma correction, focus mode, and settings. Dynamically creates `MonitorCard` widgets on refresh.
- **`MonitorCard(QFrame)`** — Per-monitor control widget with brightness/contrast sliders and power/settings buttons.
- **`CalibrationDialog(QDialog)`** — Per-monitor RGB gain calibration using VCP codes (`0x16`/`0x18`/`0x1A`). Requires setting VCP `0x14 → 0x0B` to unlock User Color Mode.
- **`PatternWindow(QWidget)`** — Full-screen test patterns (10 types) for visual calibration.
- **`CalibrationWizard(QDialog)`** — Guided 6-step calibration wizard integrating `PatternWindow`.
- **`Tray(object)`** — `QSystemTrayIcon` wrapper. Enforces single-instance via `QLocalServer("LuminaControl_SingleInstance")`.

## Key Technical Details

**DDC-CI VCP codes used:**
- Brightness: `0x10`, Contrast: `0x12`
- RGB gains: Red `0x16`, Green `0x18`, Blue `0x1A`
- Power: `0xD6` (1=on, 5=standby)
- Color preset/user mode: `0x14` (set to `0x0B` before RGB adjustments)

**Monitor detection:** `monitorcontrol.get_monitors()` for DDC-CI handles; `screeninfo.get_monitors()` for geometry. These two lists are matched by index, so order matters.

**Gamma correction:** Windows `gdi32.dll SetDeviceGammaRamp()` — writes 256-entry RGB lookup tables per channel. This affects the GPU output independently of DDC-CI.

**Sync modes:** Master/slave model — one monitor is master, others follow absolutely or with per-monitor brightness/contrast offsets.

**Focus mode:** Polls active window every 500ms (`win32api`), dims inactive monitors by a configurable amount, restoring on focus change.

**Persistence:** `profiles.json` in `%APPDATA%\LuminaControl\` stores brightness/contrast snapshots as `{saved_at, monitors: [{index, brightness, contrast}]}`.

## Build Configuration

- `LuminaControl.spec` — PyInstaller spec (bundles `multiscreen_tray.py` + `icon.png`, no console, UPX on)
- `installer.iss` — Inno Setup config (installs to Program Files, creates Start Menu entry, optionally launches after install)
- `build.ps1` — Orchestrates icon conversion → PyInstaller → Inno Setup
