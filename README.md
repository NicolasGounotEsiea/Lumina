# Lumina Control

> Contrôle multi-écrans DDC-CI depuis la barre des tâches Windows — luminosité, contraste, calibrage RGB, correction gamma, mode jeu automatique et luminosité circadienne, le tout sans driver tiers.

---

## Fonctionnalités

| Catégorie | Détails |
|---|---|
| **DDC-CI** | Luminosité & contraste via VCP `0x10` / `0x12` ; gains RGB `0x16/0x18/0x1A` ; toutes les opérations déléguées à un `QThread` dédié par écran |
| **Gamma** | Correction GPU par écran via `SetDeviceGammaRamp` (gdi32) — indépendant du DDC-CI. Slider par carte + slider global. |
| **Sync** | Mode maître/esclave absolu ou avec décalage relatif par écran |
| **Focus** | Détection fenêtre active (win32api) ; assombrit les écrans inactifs. Délai configurable (0–5 s) pour éviter le flickering à l'Alt+Tab. |
| **Mode Jeu** | Détection plein écran automatique ; applique un préréglage bri/con sur l'écran du jeu uniquement, suspend le DDC-CI de cet écran, thème rouge dans l'UI. Priorité maximale sur Focus et Profils Auto. |
| **Luminosité circadienne** | Courbe cosinus ancrée au lever/coucher réel du soleil (algorithme NOAA). Luminosité et chaleur d'écran varient automatiquement sur 24 h. Visualisation en temps réel dans le panneau. |
| **Chaleur circadienne** | Tint chaud inversement proportionnel à la courbe de luminosité — maximum la nuit, neutre à midi solaire. Indépendant du Mode Nuit. |
| **Profils par app** | Règles automatiques déclenchées par l'application en focus (500 ms) — luminosité, contraste, gamma, gains RVB ; ciblage par écran via `MonitorFromWindow`. |
| **Colorimétrie** | Gains R/V/B DDC-CI par règle d'application, avec aperçu swatch en direct |
| **Calibrage RGB** | Dialog par écran : onglet Gains R/V/B DDC-CI + assistant guidé 6 étapes avec patterns plein écran |
| **Courbes de tons & ICC** | Éditeur de courbes tonales par canal (spline monotone Fritsch-Carlson, 256 points) appliquées via `SetDeviceGammaRamp`. Export profil ICC v2 compatible Photoshop / Lightroom / DaVinci Resolve. Les courbes se composent avec gamma et chaleur sans se perdre. |
| **Noms d'écrans (EDID)** | Résolution en deux temps : `EnumDisplayDevices` puis fallback EDID registry (`HKLM\...\DISPLAY\<model>`) — couvre tous les moniteurs PnP même sans driver EDID. |
| **Rétroéclairage WMI** | Backend WMI pour les dalles internes (laptops) sans DDC-CI. Connexion WMI mise en cache par worker (reset-on-error). |
| **Détection HDR** | `hdr.get_hdr_info()` via `DisplayConfig` API — remonte `hdr_supported` et `hdr_enabled` par écran (Windows Advanced Color). |
| **Position des écrans** | `enumerate_monitors()` calcule automatiquement Gauche / Droite / Centre / Haut / Bas / Principal selon la disposition physique. |
| **Hiérarchie visuelle** | Séparateurs de groupes étiquetés (RÉGLAGES / AUTOMATISATION / APPLICATION) dans le panneau principal. |
| **i18n** | Détection automatique FR/EN depuis la locale système (`lumina_control/i18n.py`) |
| **Snapshots** | Sauvegarde / restauration de profils dans `%APPDATA%\LuminaControl` |
| **Instance unique** | Guard via `QLocalServer` — relance = réafficher la fenêtre |
| **Assistant de démarrage** | Wizard 5 étapes avec tableau de référence rapide |
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
├── multiscreen_tray.py          # Point d'entrée legacy (shim 7 lignes)
├── lumina_control/
│   ├── __main__.py              # Entrée principale, guard single-instance
│   ├── config.py                # Constantes, palette couleur, chemins AppData
│   ├── style.py                 # Stylesheet Qt dark/light + variante gaming (rouge)
│   ├── i18n.py                  # Internationalisation — _(), FR/EN
│   ├── startup.py               # Démarrage Windows — registre HKCU Run
│   ├── updater.py               # Vérif. GitHub Releases en arrière-plan
│   ├── profiles.py              # ProfileManager — snapshots & settings JSON
│   ├── sun.py                   # Algorithme NOAA sunrise/sunset (pur Python)
│   ├── circadian.py             # CircadianEngine — courbe bri + chaleur 24 h
│   ├── curve_editor.py          # monotone_lut, compose_ramp, build_icc_bytes, write_icc_profile
│   ├── utils.py                 # Gamma (gdi32), wake monitors, fullscreen, foreground
│   ├── monitor_enumerate.py     # Énumération stable via EnumDisplayMonitors
│   ├── app_rules.py             # AppRule dataclass + AppRuleManager
│   ├── rules_engine.py          # RulesEngine — détection foreground, apply/restore
│   └── ui/
│       ├── tray.py              # QSystemTrayIcon + menu contextuel
│       ├── main_window.py       # Panneau flottant principal
│       ├── monitor_card.py      # Widget par écran (bri/con/power/calibrage/RGB)
│       ├── app_rules_dialog.py  # Dialog CRUD des profils par application
│       ├── calibration.py       # CalibrationDialog + CalibrationWizard
│       ├── patterns.py          # PatternWindow — 10 patterns plein écran
│       └── onboarding.py        # OnboardingDialog — wizard premier lancement
├── build.ps1
├── LuminaControl.spec
└── installer.iss
```

### Classes principales

| Classe | Rôle |
|---|---|
| `MainWindow` | Panneau flottant. Gère les cards, sync, gamma, focus, mode jeu, circadien, paramètres. |
| `MonitorCard` | Card par écran. Sliders bri/con/gamma, bouton power, calibrage. |
| `CircadianEngine` | Calcule la cible de luminosité et de chaleur selon la courbe sin 24 h. |
| `_CircadianCurveWidget` | Widget custom `QPainter` — courbe 24 h avec soleil/lune géométriques. |
| `CalibrationDialog` | Dialog par écran, deux onglets : Gains RGB DDC-CI et Courbes de tons (+ export ICC). |
| `_CurveWidget` | Éditeur de courbes tonales 300×185 px — clic gauche ajoute/glisse les points, clic droit retire. |
| `CalibrationWizard` | Assistant 6 étapes intégrant `PatternWindow`. |
| `Tray` | Wraps `QSystemTrayIcon`, possède `MainWindow`. |
| `ProfileManager` | Lecture/écriture JSON — snapshots, settings, profils nommés. |
| `MonitorDescriptor` | Dataclass stable : `device_name`, géométrie, handle DDC-CI, `position_hint`. |
| `AppRule` | Règle par application : process, bri, con, gamma, R, G, B, enabled. |
| `RulesEngine` | Détection foreground + apply/restore avec garde de stabilité (2 ticks). |

### Luminosité circadienne

`sun.py` implémente l'algorithme NOAA (Spencer 1971) en Python pur — zéro dépendance externe :
- Équation du temps + déclinaison solaire → angle horaire → lever/coucher en UTC
- Conversion vers l'heure civile locale via `datetime.now().astimezone().utcoffset()`
- Fallback (6 h / 20 h) en cas de nuit polaire ou soleil de minuit

`CircadianEngine` consomme ces horaires :
- `_day_factor(hour) = sin(π·t)` où `t ∈ [0,1]` entre lever et coucher → pic exact à midi solaire
- `target_brightness()` interpole entre `bri_min` et `bri_max`
- `target_warmth()` est l'inverse : maximum la nuit (`warmth_max/100`), zéro à midi
- `step()` limite le changement à `step_pct` par appel (500 ms) — transitions invisibles

### Threading DDC-CI

Chaque `MonitorCard` possède un `QThread` dédié hébergeant un `_DDCWorker`. Tous les accès DDC-CI passent par des signaux cross-thread — jamais depuis le thread principal.

- Debounce 150 ms sur les sliders bri/con
- `read_rgb()` : `QEventLoop` local + timeout 500 ms, garde `_rgb_reading` anti-réentrance
- `write_failed` signal : surface l'erreur si le moniteur est en preset OSD (Game/FPS mode bloque les écritures DDC-CI)

### Codes VCP

| Code | Fonction |
|---|---|
| `0x10` | Luminosité |
| `0x12` | Contraste |
| `0x14` | Preset couleur (→ `0x0B` pour débloquer User Color Mode) |
| `0x16` | Gain Rouge |
| `0x18` | Gain Vert |
| `0x1A` | Gain Bleu |
| `0xD6` | Power (`1`=on, `5`=standby) |

### Courbes de tons & ICC (`curve_editor.py`)

`monotone_lut(points)` — interpolation spline monotone cubique (Fritsch-Carlson 1980) → LUT 256 entrées 16 bits. Pas de ringing, garantie monotone entre les points de contrôle.

`compose_ramp(r, g, b, gamma, warmth)` — applique gamma et teinte chaude **par-dessus** les LUTs personnalisées, sans jamais les écraser. Méthode centrale de `MonitorCard._apply_ramp()`. Avec des LUTs identité, le résultat est identique à `_build_combined_ramp`.

`build_icc_bytes(r, g, b)` — profil ICC v2 minimal (9 tags, primaires sRGB adaptées D50 via Bradford) — compatible Photoshop, Lightroom, DaVinci Resolve.

### Priorité des modes (runtime)

```
Gaming  >  Focus  >  App Rules
```

- **Gaming** : entré après 2 ticks plein écran consécutifs (~1 s), sorti après 2 s. Applique le préréglage sur l'écran du jeu uniquement. Suspend DDC-CI de cet écran et le `RulesEngine`. Masque le panneau flottant.
- **Focus** : assombrit les écrans inactifs. Délai configurable avant application. Suspendu pendant le gaming.
- **App Rules** : polled uniquement si `not focus_enabled and not gaming_active_or_pending`. `gaming_active_or_pending` couvre aussi le timer de sortie (2 s) pour éviter le flickering à l'alt-tab.
- **Circadien** : suspendu pendant le gaming. La chaleur circadienne cède la main au Mode Nuit si les deux sont actifs.

### Persistance (`%APPDATA%\LuminaControl\`)

| Fichier | Contenu |
|---|---|
| `settings.json` | Tous les réglages UI (sync, gamma, focus, gaming, nuit, circadien…) |
| `profiles.json` | Snapshot rapide : `{saved_at, monitors: […]}` |
| `named_profiles.json` | Profils nommés : `{name: {monitors, gamma_values}}` |
| `app_rules.json` | Liste des `AppRule`. Défauts depuis `DEFAULT_RULES` si absent. |

---

## Roadmap

Voir les [issues ouvertes](https://github.com/NicolasGounotEsiea/Lumina/issues) pour le détail complet.

**Backend**

- [x] B1 — Correspondance stable des moniteurs via `EnumDisplayMonitors`
- [x] B2 — Écritures DDC-CI non-bloquantes (`_DDCWorker` sur `QThread`)
- [ ] B3 — Retry DDC-CI avec backoff exponentiel
- [x] B4 — Profils nommés multiples (save/load/delete)
- [x] B5 — Luminosité circadienne (courbe NOAA, chaleur inversée)
- [x] B6 — Mode nuit / température de couleur (gamma warm tint)
- [x] B7 — Règles par application
- [ ] B8 — Planification power (standby auto après idle)
- [ ] B9 — Raccourcis globaux (hotkeys système)
- [x] B10 — Vérification de mise à jour (GitHub Releases API)
- [x] B11 — Mode Jeu ciblé par écran
- [x] B12 — Backend WMI pour dalles internes (laptops sans DDC-CI)
- [x] B13 — EDID registry fallback pour les noms d'écrans
- [x] B14 — Détection HDR via DisplayConfig API

**Frontend**

- [~] F1 — Noms d'écrans (EDID registry fallback OK, personnalisation manuelle non implémentée)
- [x] F2 — Gestion des profils nommés (liste, charger, supprimer)
- [ ] F3 — Raccourcis clavier in-app
- [x] F4 — Infobulle tray avec luminosité courante
- [ ] F5 — Notifications toast
- [x] F6 — Lancement au démarrage Windows (registre)
- [x] F7 — Internationalisation FR/EN
- [x] F8 — Courbes gamma par écran indépendantes
- [x] F9 — Refonte visuelle dark/light (v1.2.0)
- [x] F10 — Fenêtre déplaçable
- [x] F11 — Hiérarchie des modes dans l'UI (badges + tooltips)
- [x] F12 — Assistant de démarrage enrichi (5 étapes)
- [x] F13 — Slider luminosité globale en temps réel
- [x] F14 — Visualisation circadienne (courbe 24 h avec soleil/lune géométriques)
- [x] F15 — Hiérarchie visuelle des sections (séparateurs de groupes étiquetés)
- [x] F16 — Éditeur de courbes tonales par canal (spline Fritsch-Carlson)
- [x] F17 — Export profil ICC v2 (compatible Photoshop, Lightroom, DaVinci Resolve)

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
