# Lumina Control

> Contrôle multi-écrans DDC-CI depuis la barre des tâches Windows — luminosité, contraste, calibrage RGB et correction gamma, le tout sans driver tiers.

---

## Fonctionnalités

| Catégorie | Détails |
|---|---|
| **DDC-CI** | Luminosité & contraste via VCP `0x10` / `0x12`; gains RGB `0x16/0x18/0x1A` |
| **Gamma** | Correction GPU indépendante via `SetDeviceGammaRamp` (gdi32) |
| **Sync** | Mode maître/esclave absolu ou avec décalage relatif par écran |
| **Focus** | Détection de la fenêtre active (win32api) ; assombrit les écrans inactifs |
| **Calibrage** | Dialog RGB par écran + assistant guidé en 6 étapes avec patterns plein écran |
| **Snapshots** | Sauvegarde / restauration de profils dans `%APPDATA%\LuminaControl` |
| **Instance unique** | Guard via `QLocalServer` — relance = réafficher la fenêtre |
| **Build** | PyInstaller + Inno Setup → installeur Windows autonome |

---

## Prérequis

- Windows 10/11
- Python 3.11+
- Écrans compatibles DDC-CI (activé dans l'OSD du moniteur)

## Installation (développement)

```bash
git clone https://github.com/NicolasGounotEsiea/Lumina.git
cd Lumina
python -m venv .venv
.venv\Scripts\activate
pip install PySide6 monitorcontrol screeninfo pywin32
python multiscreen_tray.py
```

## Build installeur

Requiert : [ImageMagick](https://imagemagick.org/), [PyInstaller](https://pyinstaller.org/), [Inno Setup 6](https://jrsoftware.org/isinfo.php)

```powershell
.\build.ps1
# → dist-installer\LuminaControlSetup.exe
```

---

## Architecture

```
Lumina/
├── multiscreen_tray.py          # Point d'entrée legacy (shim)
├── lumina_control/
│   ├── __main__.py              # Entrée principale, guard single-instance
│   ├── config.py                # Constantes couleur, chemins AppData
│   ├── style.py                 # STYLESHEET Qt complet (dark theme)
│   ├── profiles.py              # ProfileManager — snapshots & settings JSON
│   ├── utils.py                 # Gamma (gdi32), wake monitors, active screen
│   ├── monitor_enumerate.py     # Énumération stable via EnumDisplayMonitors
│   └── ui/
│       ├── tray.py              # QSystemTrayIcon + menu contextuel
│       ├── main_window.py       # Panneau flottant principal
│       ├── monitor_card.py      # Widget par écran (bri/con/power/calibrage)
│       ├── calibration.py       # CalibrationDialog + CalibrationWizard
│       └── patterns.py          # PatternWindow — patterns plein écran
├── build.ps1
├── LuminaControl.spec
└── installer.iss
```

### Classes principales

| Classe | Rôle |
|---|---|
| `MainWindow` | Panneau flottant. Gère les cards, sync, gamma, focus, paramètres. |
| `MonitorCard` | Card par écran. Sliders bri/con, bouton power, ouverture calibrage. |
| `CalibrationDialog` | Ajustement fin des gains RGB via DDC-CI. |
| `CalibrationWizard` | Assistant 6 étapes intégrant `PatternWindow`. |
| `PatternWindow` | 10 patterns plein écran pour calibrage visuel. |
| `Tray` | Wraps `QSystemTrayIcon`, possède `MainWindow`. |
| `ProfileManager` | Lecture/écriture JSON — snapshots et paramètres persistants. |
| `MonitorDescriptor` | Dataclass stable : `device_name`, géométrie, handle DDC-CI. |

### Correspondance DDC-CI ↔ écrans (B1)

Au lieu du fragile `zip(get_monitors(), si_monitors())`, `enumerate_monitors()` :

1. Appelle `EnumDisplayMonitors` → liste d'HMONITORs dans l'ordre Windows
2. Pour chaque HMONITOR, `GetNumberOfPhysicalMonitorsFromHMONITOR` détecte la présence DDC-CI
3. Assigne les handles `monitorcontrol` uniquement aux HMONITORs DDC-capables (ordre conservé)
4. La géométrie vient de `screeninfo`, matchée par `device_name` (`\\.\DISPLAY1`, etc.)

Résultat : un écran sans DDC-CI ne décale plus les handles des autres.

### Codes VCP utilisés

| Code | Fonction |
|---|---|
| `0x10` | Luminosité |
| `0x12` | Contraste |
| `0x14` | Preset couleur (→ `0x0B` pour débloquer User Color Mode) |
| `0x16` | Gain Rouge |
| `0x18` | Gain Vert |
| `0x1A` | Gain Bleu |
| `0xD6` | Power (`1`=on, `5`=standby) |

---

## Roadmap

Voir les [issues ouvertes](https://github.com/NicolasGounotEsiea/Lumina/issues) pour le détail complet.

**Backend (robustesse & nouvelles capacités)**

- [x] B1 — Correspondance stable des moniteurs via `EnumDisplayMonitors`
- [ ] B2 — Écritures DDC-CI non-bloquantes (worker QThread)
- [ ] B3 — Retry DDC-CI avec backoff exponentiel
- [ ] B4 — Profils nommés multiples (save/load/delete)
- [ ] B5 — Luminosité planifiée (règles horaires, lever/coucher)
- [ ] B6 — Mode nuit / température de couleur (gamma warm tint)
- [ ] B7 — Règles par application (auto-dim pour certains process)
- [ ] B8 — Planification power (standby auto après idle)
- [ ] B9 — Raccourcis globaux (hotkeys système)
- [ ] B10 — Vérification de mise à jour (GitHub Releases API)

**Frontend (UX & confort)**

- [ ] F1 — Noms d'écrans personnalisables
- [ ] F2 — UI de gestion des profils (liste, renommer, supprimer)
- [ ] F3 — Raccourcis clavier in-app
- [ ] F4 — Infobulle tray avec luminosité courante
- [ ] F5 — Notifications toast (save/restore confirmé)
- [ ] F6 — Lancement au démarrage Windows (registre)
- [ ] F7 — Internationalisation (i18n)
- [ ] F8 — Courbes gamma par écran indépendantes

---

## Contribuer

1. Fork → branche `feature/ma-feature`
2. Commits conventionnels : `feat:`, `fix:`, `refactor:`, `docs:`
3. PR vers `main` — la CI vérifie la syntaxe Python

---

## Licence

MIT — voir [LICENSE](LICENSE) (à ajouter).
