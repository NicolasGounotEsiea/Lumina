# Changelog

Toutes les modifications notables de Lumina Control sont documentées ici.
Format : [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

---

## [1.2.0] — 2026-04-07

### Ajouté
- **Sections collapsibles** dans le panneau principal (Moniteurs, Sync, Règles app, Profils, Paramètres) — chaque section peut être repliée pour gagner de la place.
- **Animation de fondu** à l'ouverture de la fenêtre principale (160 ms, `OutCubic`).
- **Stylesheet thématisée** dark/light dans `style.py` — variables par thème (`ac`, `bg`, `card`, `mute`, `ac_rgb`, etc.) réutilisées dans tout le stylesheet.
- **`QToolTip`** stylisé en cohérence avec le thème.
- **Sélecteurs dédiés** pour `#ProfileRow`, `#RuleRow`, `#AccentIcon`, `#SectionTitle` — suppression des styles inline restants.

### Amélioré
- **Écritures DDC-CI non-bloquantes** (B2) : `_DDCWorker` sur `QThread` dédié par moniteur. Les opérations bri/con/RGB/power s'exécutent en arrière-plan ; l'interface reste réactive même sur des moniteurs lents.
- **Debounce sliders** : les changements DDC-CI ne sont envoyés qu'après 150 ms d'inactivité (évite le flood sur DDC-CI).
- **Sliders redessinés** : rainure 4 px, poignée 14 px circulaire, remplissage en dégradé couleur d'accentuation (`rgba` thème-aware).
- **Cartes moniteur** : fond en `qlineargradient` pour un relief subtil.
- **Scrollbar** : handle transparent par défaut, visible seulement au survol / pendant le défilement.
- **Hauteur fixe du panneau de défilement** + `ScrollBarAlwaysOn` : empêche tout saut de mise en page lors du repliage/dépliage des sections.
- **Suppression des styles inline** résiduels dans `monitor_card.py`, `app_rules_dialog.py`, `calibration.py` au profit des `objectName` et sélecteurs globaux.

### Corrigé
- Disparition aléatoire d'éléments lors du scroll après avoir déplié une section (conflit `QGraphicsOpacityEffect` ↔ `QScrollArea`).
- Saut de mise en page à l'apparition de la scrollbar (`ScrollBarAsNeeded` → 6 px volés).
- Callback `finished` périmé pouvant masquer une section nouvellement ouverte lors d'un clic rapide.
- Imports inutilisés détectés par pyflakes (`ACCENT_COLOR`, `BORDER_COLOR`, `QColor`, `sl_start`) supprimés dans tous les modules.

---

## [1.1.0] — 2025

### Ajouté
- **Règles par application (B7)** : détection de la fenêtre active toutes les 500 ms via `win32api`, application automatique de luminosité / contraste / gamma / gains RVB DDC-CI.
  - Ciblage par écran (`MonitorFromWindow`) — seul l'écran contenant la fenêtre active est affecté.
  - Gains R/V/B avec aperçu swatch en direct dans le dialog de règles.
  - CRUD complet + picker des applications en cours d'exécution.
- **Vérification de mise à jour (B10)** : check non-bloquant au démarrage (QThread, délai 3 s) via l'API GitHub Releases ; bannière discrète si nouvelle version disponible.
- **Internationalisation (F7)** : module `lumina_control/i18n.py`, fonction `_()`, détection automatique FR/EN depuis la locale système.
- **Lancement au démarrage Windows (F6)** : `lumina_control/startup.py`, clé `HKCU\...\Run` (sans droits admin), checkbox dans les paramètres.
- **Gamma par écran (F8)** : slider GPU indépendant DDC-CI dans chaque `MonitorCard` via `SetDeviceGammaRamp` ; persistance dans `settings.json`.

### Amélioré
- **Correspondance stable moniteurs (B1)** : `EnumDisplayMonitors` + `GetNumberOfPhysicalMonitorsFromHMONITOR` — un écran sans DDC-CI ne décale plus les handles des autres.
- **Architecture** : découpage du monolithe `multiscreen_tray.py` en package `lumina_control/` (config, style, i18n, profiles, app_rules, utils, monitor_enumerate, ui/).

---

## [1.0.0] — 2024

- Version initiale : contrôle DDC-CI multi-écrans (luminosité, contraste), correction gamma GPU, mode focus, snapshots de profils, icône tray avec badge de luminosité, instance unique via `QLocalServer`.
