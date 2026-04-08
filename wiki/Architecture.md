# Architecture

## Structure du projet

```
screenController/
├── multiscreen_tray.py          # Point d'entrée legacy (shim vers lumina_control)
├── lumina_control/
│   ├── __main__.py              # Entrée principale + guard single-instance
│   ├── config.py                # Constantes, palette couleurs, chemins AppData
│   ├── style.py                 # Stylesheet Qt complet (dark/light, variables par thème)
│   ├── i18n.py                  # Internationalisation — fonction _(), FR/EN
│   ├── startup.py               # Démarrage Windows — registre HKCU Run
│   ├── updater.py               # Vérification GitHub Releases (non-bloquant)
│   ├── profiles.py              # ProfileManager — snapshots & settings JSON
│   ├── utils.py                 # Gamma GDI32, wake monitors, écran actif
│   ├── monitor_enumerate.py     # Énumération stable via EnumDisplayMonitors
│   ├── app_rules.py             # AppRule dataclass + AppRuleManager
│   └── ui/
│       ├── tray.py              # QSystemTrayIcon + menu contextuel
│       ├── main_window.py       # Panneau flottant principal
│       ├── monitor_card.py      # Widget par écran
│       ├── app_rules_dialog.py  # Dialog CRUD règles par application
│       ├── calibration.py       # CalibrationDialog + CalibrationWizard
│       └── patterns.py          # PatternWindow — patterns plein écran
├── .github/workflows/ci.yml     # CI : lint → build → release
├── LuminaControl.spec           # PyInstaller spec
├── installer.iss                # Inno Setup config
└── build.ps1                    # Script de build complet
```

---

## Modules principaux

### `lumina_control/__main__.py`

Point d'entrée. Initialise `QApplication`, applique le stylesheet, crée `Tray`. Implémente le **guard d'instance unique** via `QLocalServer("LuminaControl_SingleInstance")` : si une instance tourne déjà, envoie un message pour la faire remonter en premier plan et quitte.

### `lumina_control/ui/tray.py` — `Tray`

Possède le `QSystemTrayIcon` et le `MainWindow`. Construit le menu contextuel. Met à jour l'icône tray avec un badge de luminosité à chaque changement de valeur (`_make_brightness_icon`). Envoie `WM_SETICON` directement via ctypes pour mettre à jour le bouton taskbar (les fenêtres frameless ne reçoivent pas `WM_SETICON` de `setWindowIcon`).

### `lumina_control/ui/main_window.py` — `MainWindow`

Panneau flottant principal (`QWidget` frameless, `WA_TranslucentBackground`, `WA_NoSystemBackground`). Contient :
- Les `MonitorCard` créées dynamiquement à l'énumération
- Le moteur de règles par application (polling 500 ms via `QTimer`)
- La logique de synchronisation maître/esclave
- Le mode Focus (détection fenêtre active via `win32api`)
- Les profils nommés et snapshots
- La bannière de mise à jour

### `lumina_control/ui/monitor_card.py` — `MonitorCard` + `_DDCWorker`

Chaque `MonitorCard` possède un `_DDCWorker` sur un `QThread` dédié. Toutes les opérations DDC-CI (lecture bri/con au démarrage, écriture bri/con/RGB/power) sont dispatch via signaux Qt cross-thread. La carte principale reste réactive même si un écran DDC-CI est lent (jusqu'à plusieurs centaines de ms par commande).

**Debounce** : les changements de slider déclenchent un `QTimer` à 150 ms. Si le slider bouge à nouveau avant expiration, le timer repart. L'écriture DDC-CI n'a lieu qu'à l'arrêt du slider.

### `lumina_control/monitor_enumerate.py`

Remplace le fragile `zip(get_monitors(), screeninfo_monitors())`. Utilise `EnumDisplayMonitors` (WinAPI) pour obtenir la liste des HMONITORs dans l'ordre Windows, puis `GetNumberOfPhysicalMonitorsFromHMONITOR` pour détecter la présence DDC-CI. Les handles `monitorcontrol` sont assignés uniquement aux HMONITORs DDC-capables (ordre préservé), évitant le décalage causé par un écran sans DDC-CI.

### `lumina_control/style.py`

Stylesheet Qt généré dynamiquement avec des variables de thème. Deux dictionnaires `_DARK` et `_LIGHT` définissent les valeurs. La fonction `build(theme)` applique les variables via `.format(**vars)` et retourne la stylesheet complète.

Variables principales : `bg`, `card`, `card_top`, `chov`, `bord`, `bacc`, `txt`, `mute`, `ac`, `asu`, `ac_rgb`.

---

## Flux de données

```
Slider bri (main thread)
  → _pending_bri = v
  → QTimer.start(150ms)
    → _apply_changes()
      → _sig_bri_con.emit(bri, con)   ← signal Qt cross-thread
        → _DDCWorker.apply_bri_con()  ← exécuté sur worker thread
          → monitor.set_luminance(bri)
          → monitor.set_contrast(con)
```

```
QTimer 500ms (main thread)
  → win32api.GetForegroundWindow()
  → win32process.GetWindowThreadProcessId()
  → Comparer process avec AppRules
  → Si match : apply_rule_values() sur la MonitorCard concernée
```

---

## Codes VCP utilisés

| Code | Fonction |
|---|---|
| `0x10` | Luminosité |
| `0x12` | Contraste |
| `0x14` | Preset couleur → `0x0B` pour User Color Mode |
| `0x16` | Gain Rouge |
| `0x18` | Gain Vert |
| `0x1A` | Gain Bleu |
| `0xD6` | Power (`1` = on, `5` = standby) |

---

## Persistance

Toutes les données sont stockées dans `%APPDATA%\LuminaControl\` :

| Fichier | Contenu |
|---|---|
| `profiles.json` | Snapshot rapide (luminosité + contraste par écran) |
| `settings.json` | Paramètres applicatifs (sync, gamma, focus, nuit…) |
| `app_rules.json` | Règles par application |
| `named_profiles.json` | Profils nommés (luminosité + contraste + gamma par écran) |

---

## Internationalisation

Le module `i18n.py` expose la fonction `_()`. À l'initialisation, il détecte la locale système (`locale.getdefaultlocale()`) et charge le dictionnaire FR ou EN. Toutes les chaînes UI passent par `_()`.

Pour ajouter une langue, ajouter une entrée dans le dictionnaire `_TRANSLATIONS` dans `i18n.py`.
