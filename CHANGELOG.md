# Changelog

Toutes les modifications notables de Lumina Control sont documentées ici.
Format : [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

---

## [1.2.2] — 2026-04-11

### Ajouté
- **Position des écrans** : `enumerate_monitors()` calcule automatiquement l'étiquette de position (Gauche / Droite / Centre / Haut / Bas / Principal) à partir de la géométrie Windows. Apparaît sur chaque carte, dans le dropdown de synchronisation et dans le wizard. Gère les setups côte à côte (axe X) et empilés (axe Y).
- **Fenêtre déplaçable** : glisser depuis la barre de titre repositionne le panneau flottant. Le drag est limité à la zone titre via hit-test sur `_title_bar` — les sliders et boutons du contenu ne sont pas affectés.
- **Priorité des modes dans l'UI** : badge "⚠ Suspendu" visible dans la section Mode Focus quand le Mode Jeu est actif. Tooltips sur les boutons de bascule Focus et Gaming décrivant la hiérarchie (Gaming > Focus > Profils Auto).
- **Assistant de démarrage enrichi** : 5 étapes au lieu de 4 — ajout d'une page "Contrôle des écrans" (luminosité globale, sync, focus, nuit) et d'une page "Fonctions avancées" (mode jeu, profils app, profils nommés, sauvegarde rapide, calibrage). La page finale inclut un tableau de référence rapide "où trouver chaque fonction". Tip DDC-CI : indique que le scan est relançable via ↻.
- **Tooltips Gamma** : survol du slider `γ Gamma` sur chaque carte affiche une explication en langage clair (rôle GPU, valeurs de référence, différence avec le GAMMA GPU global). Description ajoutée dans l'en-tête de la section GAMMA GPU.

### Amélioré
- **Slider luminosité globale en temps réel** : connecté sur `valueChanged` au lieu de `sliderReleased`. Les cartes suivent le curseur pendant le glissement ; les debounce 150 ms des cards protègent le bus DDC-CI contre le flood.
- **`read_rgb()` asynchrone** : la lecture des gains RGB est maintenant déléguée au `_DDCWorker` via un signal cross-thread. Un `QEventLoop` local avec timeout 500 ms évite tout gel de l'UI. Un garde `_rgb_reading` empêche la ré-entrance depuis le poll timer.

### Corrigé
- Thread de scan DDC-CI de l'onboarding non nettoyé : `deleteLater()` connecté au signal `finished` du `QThread`.

---

## [1.2.1] — 2026-04-08

### Ajouté
- **Mode Jeu** : détection automatique du plein écran (comparaison rect fenêtre ↔ rect moniteur via `GetMonitorInfoW`). Quand un jeu passe en plein écran, applique un préréglage luminosité/contraste configurable puis suspend les écritures DDC-CI pour ne pas interrompre le jeu. Rétablit les valeurs d'origine à la sortie du plein écran.
- **Thème rouge** : toute l'interface bascule en rouge dès l'activation du mode jeu (`get_stylesheet(gaming=True)`).
- **`is_fullscreen_foreground()`** dans `utils.py` — détecte le plein écran via comparaison des rects sans dépendance externe.
- **DDC suspension** dans `MonitorCard` : flag `_ddc_suspended` + méthode `set_ddc_suspended()` — les sliders accumulent les changements, qui sont vidés à la reprise.
- Section **MODE JEU** dans le panneau principal (collapsible) avec toggle activer/désactiver et sliders de luminosité/contraste cibles.
- Entrée **Mode Jeu** dans le menu contextuel du tray (case à cocher synchronisée avec le panneau).
- La section **Profils par application** est grisée automatiquement quand le mode jeu est actif (tooltip explicatif).
- **Robustesse du mode jeu** : garde d'entrée (2 polls consécutifs ~1 s) + sortie différée (2 s) pour éviter les faux positifs et le flickering lors des chargements.
- **Assistant de démarrage** (onboarding) : dialog 4 étapes au premier lancement — bienvenue, scan DDC-CI avec résultats par écran, présentation des fonctionnalités clés, confirmation. Accessible à tout moment via Paramètres → *Assistant de démarrage…*

---

## [1.2.0] — 2026-04-08

### Ajouté
- **Sections collapsibles** dans le panneau principal (Moniteurs, Sync, Règles app, Profils, Paramètres).
- **Animation de fondu** à l'ouverture de la fenêtre principale (160 ms, `OutCubic`).
- **Stylesheet thématisée** dark/light dans `style.py` — variables par thème réutilisées dans tout le stylesheet.
- **`QToolTip`** stylisé en cohérence avec le thème.
- **Sélecteurs dédiés** pour `#ProfileRow`, `#RuleRow`, `#AccentIcon`, `#SectionTitle`.

### Amélioré
- **Écritures DDC-CI non-bloquantes (B2)** : `_DDCWorker` sur `QThread` dédié par moniteur — bri/con/RGB/power asynchrones, debounce 150 ms.
- **Sliders redessinés** : rainure 4 px, poignée 14 px, remplissage en dégradé couleur d'accentuation.
- **Cartes moniteur** : fond en `qlineargradient` pour un relief subtil.
- **Scrollbar** : handle transparent par défaut, visible seulement au survol.
- **Hauteur fixe + `ScrollBarAlwaysOn`** sur le panneau de défilement — supprime les sauts de mise en page.
- **Suppression des styles inline** résiduels au profit des `objectName` et sélecteurs globaux.

### Corrigé
- Bordure rectangulaire visible dans le `.exe` autour de la fenêtre (`WA_NoSystemBackground` + `DwmSetWindowAttribute` pour la glow border Windows 11).
- Disparition aléatoire d'éléments lors du scroll après avoir déplié une section (conflit `QGraphicsOpacityEffect` ↔ `QScrollArea`).
- Saut de mise en page à l'apparition de la scrollbar (`ScrollBarAsNeeded` → 6 px volés).
- Callback `finished` périmé pouvant masquer une section nouvellement ouverte lors d'un clic rapide.
- Imports inutilisés détectés par pyflakes (`ACCENT_COLOR`, `BORDER_COLOR`, `QColor`, `sl_start`) supprimés dans tous les modules.

---

## [1.0.0] — 2025

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
