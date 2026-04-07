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
| **Profils par app** | Règles automatiques déclenchées par l'application en focus (500 ms) — luminosité, contraste, gamma, gains RVB ; s'applique uniquement sur l'écran contenant la fenêtre |
| **Colorimétrie** | Gains R/V/B DDC-CI par règle d'application, avec aperçu swatch en direct |
| **Calibrage** | Dialog RGB par écran + assistant guidé en 6 étapes avec patterns plein écran |
| **Gamma par écran** | Slider gamma GPU indépendant dans chaque card (GDI32 `SetDeviceGammaRamp`) |
| **i18n** | Détection automatique FR/EN depuis la locale système (`lumina_control/i18n.py`) |
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
│   ├── i18n.py                  # Internationalisation — fonction _(), FR/EN
│   ├── startup.py               # Démarrage Windows — registre HKCU Run (F6)
│   ├── updater.py               # Vérif. GitHub Releases en arrière-plan (B10)
│   ├── profiles.py              # ProfileManager — snapshots & settings JSON
│   ├── utils.py                 # Gamma (gdi32), wake monitors, active/foreground screen
│   ├── monitor_enumerate.py     # Énumération stable via EnumDisplayMonitors
│   ├── app_rules.py             # AppRule dataclass + AppRuleManager (persistance JSON)
│   └── ui/
│       ├── tray.py              # QSystemTrayIcon + menu contextuel
│       ├── main_window.py       # Panneau flottant principal + moteur de règles
│       ├── monitor_card.py      # Widget par écran (bri/con/power/calibrage/RGB)
│       ├── app_rules_dialog.py  # Dialog CRUD des profils par application
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
| `AppRule` | Règle par application : process, bri, con, gamma, R, G, B, enabled. |
| `AppRuleManager` | Chargement/sauvegarde des règles dans `app_rules.json`. |

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
- [x] B2 — Écritures DDC-CI non-bloquantes (worker QThread)
  - [x] `_DDCWorker` sur `QThread` dédié par écran — bri/con/RGB/power asynchrones
  - [x] Debounce 150 ms sur les sliders pour éviter le flood DDC-CI
- [ ] B3 — Retry DDC-CI avec backoff exponentiel
- [ ] B4 — Profils nommés multiples (save/load/delete)
- [ ] B5 — Luminosité planifiée (règles horaires, lever/coucher)
- [ ] B6 — Mode nuit / température de couleur (gamma warm tint)
- [x] B7 — Règles par application (auto-dim/calibrage pour certains process)
  - [x] Détection foreground process 500 ms + garde de stabilité
  - [x] Luminosité, contraste, gamma, gains RVB DDC-CI par règle
  - [x] Ciblage par écran (`MonitorFromWindow`) — seul l'écran actif est affecté
  - [x] Colorimétrie R/V/B avec aperçu swatch en direct
  - [x] CRUD complet + picker d'apps en cours
- [ ] B8 — Planification power (standby auto après idle)
- [ ] B9 — Raccourcis globaux (hotkeys système)
- [x] B10 — Vérification de mise à jour (GitHub Releases API)
  - [x] Check non-bloquant au démarrage (QThread, délai 3 s)
  - [x] Bannière discrète avec bouton "Télécharger" si nouvelle version détectée

**Frontend (UX & confort)**

- [ ] F1 — Noms d'écrans personnalisables
- [ ] F2 — UI de gestion des profils (liste, renommer, supprimer)
- [ ] F3 — Raccourcis clavier in-app
- [ ] F4 — Infobulle tray avec luminosité courante
- [ ] F5 — Notifications toast (save/restore confirmé)
- [x] F6 — Lancement au démarrage Windows (registre)
  - [x] `lumina_control/startup.py` — lecture/écriture `HKCU\...\Run`
  - [x] Checkbox dans la section PARAMÈTRES (pas d'admin requis)
- [x] F7 — Internationalisation (i18n)
  - [x] Module `lumina_control/i18n.py` — fonction `_()`, détection de locale, FR/EN
  - [x] Toutes les chaînes UI traduites (tray, main_window, monitor_card, app_rules_dialog, calibration)
- [x] F8 — Courbes gamma par écran indépendantes
  - [x] Slider gamma dans chaque `MonitorCard` (GPU, indépendant DDC-CI)
  - [x] Persistance par écran dans `settings.json` (`gamma_values`)
  - [x] Slider global GAMMA GPU = raccourci « appliquer à tous »
- [x] F9 — Refonte visuelle complète (v1.2.0)
  - [x] Stylesheet thématisée dark/light avec variables CSS-like (`style.py`)
  - [x] Sections collapsibles dans le panneau principal
  - [x] Cartes avec dégradé de fond subtil
  - [x] Sliders redessinés — rainure 4 px, poignée 14 px, remplissage couleur d'accentuation
  - [x] Scrollbar transparente par défaut, visible au survol
  - [x] `QToolTip` stylisé
  - [x] Animation de fondu à l'ouverture de la fenêtre

---

## Contribuer

1. Fork → branche `feature/ma-feature`
2. Commits conventionnels : `feat:`, `fix:`, `refactor:`, `docs:`
3. PR vers `main` — la CI vérifie la syntaxe Python

---

## Changelog

Voir [CHANGELOG.md](CHANGELOG.md) pour l'historique détaillé des versions.

---

## Licence

Propriétaire — voir [LICENSE](LICENSE).
Tous droits réservés © 2024-2026 Nicolas Gounot.
Usage personnel sur une machine par licence achetée. Redistribution et décompilation interdites.
