# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Lumina Control** (v1.2.2) is a Windows desktop system tray application for controlling multi-monitor brightness, contrast, and color calibration via DDC-CI protocol.

The application is structured as the `lumina_control` Python package. `multiscreen_tray.py` at the root is a 7-line legacy shim that simply calls `lumina_control.__main__.main()` — **all logic lives in the package**.

## Commands

**Run the application:**
```bash
python multiscreen_tray.py
# or equivalently:
python -m lumina_control
```

**Lint (run before committing):**
```bash
python -m pyflakes lumina_control/
```

**Build standalone executable + installer:**
```powershell
.\build.ps1
```
Requires ImageMagick (icon generation), PyInstaller, and Inno Setup 6 (`C:\Program Files (x86)\Inno Setup 6\ISCC.exe`).
Output: `dist-installer\LuminaControlSetup.exe`.

**Install dependencies** (no `requirements.txt` — infer from `.venv`):
```bash
pip install PySide6 monitorcontrol screeninfo pywin32
```

## Package Structure

```
lumina_control/
├── __main__.py              # Entry point: single-instance guard (QLocalServer),
│                            #   QApplication setup, theme polling, first-run onboarding
├── config.py                # APP_VERSION, colour palette, AppData path helpers
├── style.py                 # Full Qt stylesheet — dark/light + gaming (red) variants
├── i18n.py                  # _() function, FR/EN dict, auto-detect from system locale
├── startup.py               # Windows startup via HKCU\...\Run (no admin required)
├── updater.py               # Non-blocking GitHub Releases check (QThread, 3 s delay)
├── profiles.py              # ProfileManager — snapshots, settings.json, named_profiles.json
├── monitor_enumerate.py     # enumerate_monitors() — stable DDC↔geometry matching +
│                            #   position hints (Gauche/Droite/Principal…)
├── app_rules.py             # AppRule dataclass + AppRuleManager (app_rules.json)
├── rules_engine.py          # RulesEngine — foreground process detection, rule apply/restore
├── utils.py                 # set_device_gamma (GDI32), wake monitors, active screen,
│                            #   fullscreen detection, foreground process/window
└── ui/
    ├── tray.py              # Tray — QSystemTrayIcon, context menu, owns MainWindow
    ├── main_window.py       # MainWindow — floating panel, all sections, poll timer
    ├── monitor_card.py      # MonitorCard + _DDCWorker (async DDC-CI per monitor)
    ├── calibration.py       # CalibrationDialog (RGB gains) + CalibrationWizard (6 steps)
    ├── patterns.py          # PatternWindow — 10 fullscreen test patterns
    ├── app_rules_dialog.py  # CRUD dialog for per-app profiles
    └── onboarding.py        # OnboardingDialog — 5-step first-run wizard
```

## Key Classes

| Class | File | Role |
|---|---|---|
| `MainWindow` | `ui/main_window.py` | Floating panel. Owns all `MonitorCard`s, sync logic, gamma, focus, gaming, app rules UI, settings persistence. Poll timer every 500 ms. |
| `MonitorCard` | `ui/monitor_card.py` | Per-monitor card. Sliders bri/con/gamma, power button, calibration opener. Owns a `_DDCWorker` on a dedicated `QThread`. |
| `_DDCWorker` | `ui/monitor_card.py` | Serialises all DDC-CI ops (bri/con write, RGB write/read, power) on a worker thread. Connected via cross-thread signals. |
| `RulesEngine` | `rules_engine.py` | Detects foreground process every 500 ms, matches `AppRule`s, applies/restores values. Stability guard: 2 consecutive ticks before firing. |
| `Tray` | `ui/tray.py` | `QSystemTrayIcon` wrapper. Context menu mirrors panel toggles. |
| `ProfileManager` | `profiles.py` | JSON read/write for snapshots, settings, named profiles. Merges missing keys with `DEFAULT_SETTINGS` on load. |
| `MonitorDescriptor` | `monitor_enumerate.py` | Dataclass: `index`, `device_name`, `x/y/width/height`, `is_primary`, `hz`, `ddc_handle`, `position_hint`. |
| `AppRule` | `app_rules.py` | Dataclass: `process`, `label`, `brightness`, `contrast`, `gamma`, `red`, `green`, `blue`, `enabled`. |
| `OnboardingDialog` | `ui/onboarding.py` | 5-step first-run wizard (welcome, DDC scan, screen control, advanced features, summary). |

## Key Technical Details

### DDC-CI threading model

Every `MonitorCard` owns a `_DDCWorker` moved to a `QThread`. **All DDC-CI operations are async**:

- Bri/con writes: `_sig_bri_con` signal → `apply_bri_con` slot, with 150 ms debounce on sliders.
- RGB writes: `_sig_rgb` / `_sig_rgb_dict` signals → `apply_rgb` / `apply_rgb_dict` slots.
- **RGB reads**: `_sig_read_rgb` signal → `read_rgb` slot → `rgb_read_done` signal back to main thread. `MonitorCard.read_rgb()` uses a local `QEventLoop` + 500 ms timeout to await the result without blocking the UI. Re-entrance guard: `_rgb_reading` flag.
- Power: `_sig_power` signal → `apply_power` slot.

Never call DDC-CI APIs directly from the main thread. Use the worker signals.

### VCP codes

| Code | Function |
|---|---|
| `0x10` | Brightness |
| `0x12` | Contrast |
| `0x14` | Colour preset → set to `0x0B` to unlock User Colour mode before RGB adjustments |
| `0x16` | Red gain |
| `0x18` | Green gain |
| `0x1A` | Blue gain |
| `0xD6` | Power (`1` = on, `5` = standby) |

### Monitor enumeration (`monitor_enumerate.py`)

`enumerate_monitors()` avoids the fragile index-zip approach:

1. `EnumDisplayMonitors` → ordered list of HMONITORs.
2. `GetNumberOfPhysicalMonitorsFromHMONITOR` → detects DDC-CI presence per HMONITOR.
3. `monitorcontrol` handles assigned only to DDC-capable HMONITORs (order preserved).
4. Geometry from `screeninfo`, matched by `device_name` (`\\.\DISPLAY1`, etc.).
5. `_attach_position_hints()` computes `position_hint` (Gauche/Droite/Centre or Haut/Bas for vertical stacks, plus Principal for the primary monitor).

`MonitorDescriptor.label` incorporates `position_hint`: `"Écran 1  —  Gauche  ·  Principal"`.

### Gamma correction

`set_device_gamma(device_name, gamma, warmth)` in `utils.py` writes a 256-entry RGB LUT via `gdi32.SetDeviceGammaRamp`. Operates on the GPU output, entirely independent of DDC-CI. Warmth (0.0–1.0) reduces the blue channel to produce a warm tint for night mode.

Per-monitor gamma is stored in `settings.json` under `gamma_values: {device_name: float}`. Reset on clean exit (`reset_gamma()` connected to `app.aboutToQuit`).

### Mode priority (runtime)

Gaming mode > Focus mode > App Rules (Sync also suspended by both).

- **Gaming mode** (`_gaming_active`): entered after 2 consecutive fullscreen ticks (~1 s), exited after 2 s of non-fullscreen. Applies gaming preset, then suspends DDC writes (`set_ddc_suspended(True)`). Suspends `RulesEngine`. Conflict badges shown in Focus and App Rules sections.
- **Focus mode**: polls active screen index every 500 ms, dims inactive monitors. Suspended while gaming is active (DDC writes are blocked by suspension).
- **App Rules**: polled only when `not focus_enabled and not _gaming_active`.

### Persistence files (all in `%APPDATA%\LuminaControl\`)

| File | Content |
|---|---|
| `settings.json` | All UI state (sync, gamma, focus, gaming, night mode, app_rules_enabled…) |
| `profiles.json` | Quick snapshot: `{saved_at, monitors: [{device_name, index, brightness, contrast}]}` |
| `named_profiles.json` | Named profiles: `{name: {monitors: […], gamma_values: {device_name: float}}}` |
| `app_rules.json` | List of `AppRule` dicts. Defaults from `app_rules.py:DEFAULT_RULES` if missing. |

### Internationalisation

`lumina_control/i18n.py` exposes `_(text)`. French is the source language; `_EN` dict maps every French string to English. Language detected once at import from `locale.getdefaultlocale()`. Always wrap UI strings with `_()`. **No duplicate keys allowed in `_EN`** — pyflakes catches them.

### Theme / stylesheet

`style.py:get_stylesheet(dark, gaming)` returns the full stylesheet. Called on startup and whenever the Windows theme changes (polled every 5 s) or gaming mode is toggled. Dark palette is the default; light palette mirrors Windows 11 Fluent Design colours.

### Single-instance guard

`__main__.py` probes `QLocalServer("LuminaControl_SingleInstance")` before creating the app. If the server responds, sends `b"activate"` and exits. The running instance's server calls `show_and_activate()` on the main window.

## Build Configuration

- `LuminaControl.spec` — PyInstaller spec: bundles `lumina_control/` package + `icon.png`, no console window, UPX compression on.
- `installer.iss` — Inno Setup 6: installs to `Program Files\Lumina Control`, Start Menu entry, optional desktop shortcut, optional launch after install. Version string must match `config.py:APP_VERSION`.
- `build.ps1` — Orchestrates: ImageMagick icon conversion → PyInstaller → Inno Setup.

**When bumping the version**, update both:
1. `lumina_control/config.py` → `APP_VERSION`
2. `installer.iss` → `AppVersion`
