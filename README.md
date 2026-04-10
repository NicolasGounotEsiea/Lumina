# Lumina Control

> Contrôle multi-écrans DDC-CI depuis la barre des tâches Windows — luminosité, contraste, calibrage RGB, correction gamma et mode jeu automatique, le tout sans driver tiers.

---

## Fonctionnalités

| Catégorie | Détails |
|---|---|
| **DDC-CI** | Luminosité & contraste via VCP `0x10` / `0x12`; gains RGB `0x16/0x18/0x1A`; toutes les opérations DDC-CI (y compris lecture RGB) déléguées à un `QThread` dédié par écran |
| **Gamma** | Correction GPU par écran via `SetDeviceGammaRamp` (gdi32) — indépendant du DDC-CI. Slider par card + slider global "appliquer à tous". Tooltip explicatif sur chaque slider. |
| **Sync** | Mode maître/esclave absolu ou avec décalage relatif par écran |
| **Focus** | Détection de la fenêtre active (win32api) ; assombrit les écrans inactifs. Badge de conflit visible si le Mode Jeu suspend le Mode Focus. |
| **Mode Jeu** | Détection plein écran automatique (`GetMonitorInfoW`) ; applique un préréglage bri/con, suspend les écritures DDC-CI pendant la session, thème rouge dans l'UI. Priorité maximale sur Focus et Profils Auto. |
| **Profils par app** | Règles automatiques déclenchées par l'application en focus (500 ms) — luminosité, contraste, gamma, gains RVB ; s'applique uniquement sur l'écran contenant la fenêtre |
| **Colorimétrie** | Gains R/V/B DDC-CI par règle d'application, avec aperçu swatch en direct |
| **Calibrage** | Dialog RGB par écran + assistant guidé en 6 étapes avec patterns plein écran |
| **Position des écrans** | `enumerate_monitors()` calcule automatiquement Gauche / Droite / Centre / Haut / Bas / Principal selon la disposition physique. Labels visibles dans le panneau, le dropdown de sync et le wizard. |
| **Fenêtre déplaçable** | Glisser depuis la barre de titre repositionne le panneau flottant. Drag limité à la zone titre pour ne pas interférer avec les sliders. |
| **Priorité des modes** | Hiérarchie Gaming > Focus > Profils Auto documentée dans l'UI : badges "⚠ Suspendu" dans chaque section concernée + tooltips sur les boutons de bascule. |
| **i18n** | Détection automatique FR/EN depuis la locale système (`lumina_control/i18n.py`) |
| **Snapshots** | Sauvegarde / restauration de profils dans `%APPDATA%\LuminaControl` |
| **Instance unique** | Guard via `QLocalServer` — relance = réafficher la fenêtre |
| **Assistant de démarrage** | Wizard 5 étapes : bienvenue, scan DDC-CI, contrôle des écrans, fonctions avancées, récapitulatif. Couvre toutes les fonctionnalités avec un tableau de référence rapide. |
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
│   ├── style.py                 # Stylesheet Qt dark/light + variante gaming (rouge)
│   ├── i18n.py                  # Internationalisation — fonction _(), FR/EN
│   ├── startup.py               # Démarrage Windows — registre HKCU Run (F6)
│   ├── updater.py               # Vérif. GitHub Releases en arrière-plan (B10)
│   ├── profiles.py              # ProfileManager — snapshots & settings JSON
│   ├── utils.py                 # Gamma (gdi32), wake monitors, active/foreground screen, fullscreen detection
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
| `MainWindow` | Panneau flottant. Gère les cards, sync, gamma, focus, mode jeu, paramètres. |
| `MonitorCard` | Card par écran. Sliders bri/con, bouton power, ouverture calibrage. |
| `CalibrationDialog` | Ajustement fin des gains RGB via DDC-CI. |
| `CalibrationWizard` | Assistant 6 étapes intégrant `PatternWindow`. |
| `PatternWindow` | 10 patterns plein écran pour calibrage visuel. |
| `Tray` | Wraps `QSystemTrayIcon`, possède `MainWindow`. |
| `ProfileManager` | Lecture/écriture JSON — snapshots et paramètres persistants. |
| `MonitorDescriptor` | Dataclass stable : `device_name`, géométrie, handle DDC-CI, `position_hint` (Gauche/Droite/Principal…). |
| `AppRule` | Règle par application : process, bri, con, gamma, R, G, B, enabled. |
| `AppRuleManager` | Chargement/sauvegarde des règles dans `app_rules.json`. |

### Correspondance DDC-CI ↔ écrans (B1)

Au lieu du fragile `zip(get_monitors(), si_monitors())`, `enumerate_monitors()` :

1. Appelle `EnumDisplayMonitors` → liste d'HMONITORs dans l'ordre Windows
2. Pour chaque HMONITOR, `GetNumberOfPhysicalMonitorsFromHMONITOR` détecte la présence DDC-CI
3. Assigne les handles `monitorcontrol` uniquement aux HMONITORs DDC-capables (ordre conservé)
4. La géométrie vient de `screeninfo`, matchée par `device_name` (`\\.\DISPLAY1`, etc.)
5. `_attach_position_hints()` calcule Gauche/Droite/Centre (ou Haut/Bas pour setups empilés) et marque le principal

Résultat : un écran sans DDC-CI ne décale plus les handles des autres ; chaque écran est identifiable par sa position physique.

### Threading DDC-CI (`_DDCWorker`)

Chaque `MonitorCard` possède un `QThread` dédié hébergeant un `_DDCWorker`. Tous les accès DDC-CI (bri/con, RGB, power, **lecture RGB**) passent par des signaux cross-thread et s'exécutent sur le worker sans bloquer l'UI.

- `read_rgb()` utilise un `QEventLoop` local + timeout 500 ms — le thread principal reste réactif pendant la lecture.
- Un garde `_rgb_reading` empêche la ré-entrance si le poll timer se déclenche pendant l'attente.
- Les sliders bri/con ont un debounce de 150 ms ; le slider global `Luminosité globale` applique en temps réel sur `valueChanged`, les cards absorbent le flood via leur propre debounce.

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
- [x] B4 — Profils nommés multiples (save/load/delete)
  - [x] Sauvegarde/restauration/suppression depuis le panneau principal
  - [x] Persistance luminosité, contraste et gamma par écran dans `named_profiles.json`
- [ ] B5 — Luminosité planifiée (règles horaires, lever/coucher)
- [x] B6 — Mode nuit / température de couleur (gamma warm tint)
  - [x] Slider de chaleur (0–100) combiné à la correction gamma via `SetDeviceGammaRamp`
  - [x] Persistance dans `settings.json`
- [x] B11 — Mode Jeu
  - [x] Détection plein écran via comparaison rect fenêtre ↔ rect moniteur (`GetMonitorInfoW`)
  - [x] Préréglage bri/con configurable appliqué à l'entrée en plein écran
  - [x] Suspension des écritures DDC-CI pendant la session (pas d'interruption bus I²C)
  - [x] Thème rouge complet dans l'UI dès l'activation du mode
  - [x] Grise automatiquement les profils par application (conflit évité)
  - [x] Entrée dans le menu tray synchronisée avec le panneau principal
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

- [~] F1 — Noms d'écrans personnalisables
  - [x] Labels automatiques Gauche / Droite / Centre / Haut / Bas / Principal calculés depuis la géométrie Windows
  - [ ] Noms entièrement personnalisables par l'utilisateur (non implémenté)
- [x] F2 — UI de gestion des profils (liste, renommer, supprimer)
  - [x] Inclus dans B4 — liste avec chargement et suppression dans le panneau principal
- [ ] F3 — Raccourcis clavier in-app
- [x] F4 — Infobulle tray avec luminosité courante
  - [x] `tray.setToolTip(f"Lumina Control — {brightness}%")` mis à jour à chaque changement
- [ ] F5 — Notifications toast (save/restore confirmé)
- [x] F6 — Lancement au démarrage Windows (registre)
  - [x] `lumina_control/startup.py` — lecture/écriture `HKCU\...\Run`
  - [x] Checkbox dans la section PARAMÈTRES (pas d'admin requis)
- [x] F7 — Internationalisation (i18n)
  - [x] Module `lumina_control/i18n.py` — fonction `_()`, détection de locale, FR/EN
  - [x] Toutes les chaînes UI traduites (tray, main_window, monitor_card, app_rules_dialog, calibration, onboarding)
- [x] F8 — Courbes gamma par écran indépendantes
  - [x] Slider gamma dans chaque `MonitorCard` (GPU, indépendant DDC-CI)
  - [x] Persistance par écran dans `settings.json` (`gamma_values`)
  - [x] Slider global GAMMA GPU = raccourci « appliquer à tous »
  - [x] Tooltip explicatif sur chaque slider (diff per-card vs global, valeurs de référence)
  - [x] Description contextuelle dans la section GAMMA GPU
- [x] F9 — Refonte visuelle complète (v1.2.0)
  - [x] Stylesheet thématisée dark/light avec variables CSS-like (`style.py`)
  - [x] Sections collapsibles dans le panneau principal
  - [x] Cartes avec dégradé de fond subtil
  - [x] Sliders redessinés — rainure 4 px, poignée 14 px, remplissage couleur d'accentuation
  - [x] Scrollbar transparente par défaut, visible au survol
  - [x] `QToolTip` stylisé
  - [x] Animation de fondu à l'ouverture de la fenêtre
- [x] F10 — Fenêtre déplaçable (drag-to-move)
  - [x] `mousePressEvent` / `mouseMoveEvent` / `mouseReleaseEvent` sur `MainWindow`
  - [x] Drag actif uniquement dans la zone titre (`_title_bar`) — ne perturbe pas les sliders
- [x] F11 — Lisibilité de la priorité des modes dans l'UI
  - [x] Badge "⚠ Suspendu — Mode Jeu actif" dans les sections Focus, Sync et Profils Auto
  - [x] Tooltip sur btn_focus : explique que le Mode Jeu le suspend automatiquement
  - [x] Tooltip sur btn_gaming : explique la priorité maximale sur Focus et Profils Auto
- [x] F12 — Assistant de démarrage enrichi
  - [x] 5 étapes au lieu de 4 : bienvenue, DDC-CI, contrôle des écrans, fonctions avancées, récapitulatif
  - [x] Tableau de référence rapide ("où trouver chaque fonction") sur la page finale
  - [x] Tip DDC-CI : indique que le scan est relançable via ↻
  - [x] Cleanup du thread de scan (`deleteLater` sur le `QThread`)
- [x] F13 — Slider luminosité globale en temps réel
  - [x] Connecté sur `valueChanged` (au lieu de `sliderReleased`) — les cards suivent le curseur en live
  - [x] Les debounce 150 ms des cards absorbent le flood et protègent le bus DDC-CI

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
