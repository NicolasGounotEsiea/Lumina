# Changelog

Toutes les modifications notables de Lumina Control sont documentées ici.
Format : [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

---

## [1.2.5] — 2026-04-15

### Ajouté
- **Système de licence Ed25519** : activation hors ligne complète par clé cryptographique. La clé `{payload_b64}.{sig_b64}` est vérifiée localement via la clé publique embarquée — aucun serveur requis. Persistance dans le registre Windows (`HKCU\SOFTWARE\LuminaControl\LicenseKey`). Binding machine optionnel (SHA256 du `MachineGuid`).
- **Dialog d'activation** (`LicenseDialog`) : s'affiche au premier lancement si aucune licence valide n'est détectée. Champ de saisie de la clé, affichage de l'ID machine, message d'erreur explicite. L'application se ferme proprement si l'activation est annulée.
- **Outil de génération de clés** (`gen_license.py`) : sous-commandes `keygen` (génère la paire Ed25519) et `issue` (signe une clé pour un email + plan donné).
- **Raccourci global Ctrl+Alt+G** : bascule le Mode Jeu sans alt-tabber, depuis n'importe quelle application. Affiché dans la liste des raccourcis du panneau Paramètres.
- **Scripts Pipedream** (`pipedream/`) : automatisation complète de la délivrance de licence — étape 1 extraction webhook LemonSqueezy, étape 2 génération Ed25519, étape 3 envoi email HTML via Gmail SMTP.

### Corrigé
- **Heures circadiennes hors fuseau local** : les villes comme New York affichaient des horaires décalés (ex. "levé 12h31") car `sun_times()` utilisait l'offset UTC de la machine. Corrigé via `zoneinfo` + `tzdata` — chaque ville utilise son propre fuseau IANA.
- **Imports inutilisés** : `ACCENT_COLOR` et `TEXT_MUTED` retirés de `onboarding.py` et `schedules_dialog.py` (signalés par pyflakes).

---

## [1.2.4] — 2026-04-12

### Ajouté
- **Luminosité circadienne** : nouvelle section AUTOMATISATION. Courbe cosinus (`sin(π·t)`) ancrée aux horaires réels de lever/coucher du soleil via l'algorithme NOAA (Spencer 1971) — pur Python, zéro dépendance externe. Picker de 20 villes + coordonnées personnalisées. Sliders bri. min / bri. max. Suspendu automatiquement en Mode Jeu.
- **Chaleur circadienne** : tint chaud (GDI32 `SetDeviceGammaRamp`) inversement proportionnel à la courbe de luminosité — maximum la nuit, neutre à midi solaire. Toggle + slider `Chaleur max` dédiés. Cède la main au Mode Nuit si les deux sont actifs.
- **Visualisation circadienne** : widget `_CircadianCurveWidget` dessiné au `QPainter` — fond `#2B2B2B` (cohérent avec les cards), zones nuit assombries, courbe remplie en dégradé ambre, grille 00/06/12/18 h, marqueurs lever/coucher pointillés, indicateur temps réel (ligne accent `#60CDFF` + dot), soleil géométrique (cercle + 8 rayons) ou croissant de lune tracé par soustraction de paths.
- **Hiérarchie visuelle** : séparateurs de groupes étiquetés (`RÉGLAGES` / `AUTOMATISATION` / `APPLICATION`) remplaçant les lignes anes entre les sections.
- **Restauration à la désactivation** : désactiver la luminosité circadienne restaure instantanément la luminosité et la chaleur d'avant l'activation.
- **Heures lever/coucher corrigées** : le calcul utilisait `lon/15` comme offset UTC (heure solaire locale) au lieu de l'offset civil réel. Corrigé via `datetime.now().astimezone().utcoffset()` — les horaires correspondent maintenant à l'heure murale (ex. Paris UTC+2 en été).
- **Formule de courbe corrigée** : `(1−cos(π·t))/2` donnait un pic au coucher du soleil, pas à midi. Remplacé par `sin(π·t)` — pic exact à midi solaire pour la luminosité et minimum à midi pour la chaleur.
- **Label cible enrichi** : quand la chaleur circadienne est active, le label affiche `Cible : X% · chaleur Y%` pour confirmer les deux valeurs calculées en temps réel.

### Amélioré
- **Badge `ValueBadge` chaleur** : `setFixedWidth` 34 → 40 px + `AlignRight` pour l'aligner avec les autres badges de sliders.

---

## [1.2.3] — 2026-04-11

### Ajouté
- **Délai Focus** : slider 0–5 s dans la section MODE FOCUS. Quand un changement d'écran actif est détecté, l'atténuation est retardée de ce délai avant de s'appliquer — évite le flickering lors d'un Alt+Tab rapide. 0 s = comportement immédiat (défaut). Persisté dans `settings.json`.
- **Exclusions du Mode Jeu** : champ texte dans la section MODE JEU pour lister les processus exclus (séparés par des virgules). Ces processus ne déclenchent jamais le mode jeu même en plein écran — utile pour `afterfx.exe` (rendus After Effects), `resolve.exe`, etc. Valeur par défaut : `afterfx.exe`. Persisté dans `settings.json`.
- **`afterfx.exe` dans les règles par défaut** : règle `After Effects — bri 80 %, con 55 %, γ 1.0` ajoutée à `DEFAULT_RULES` pour les nouveaux utilisateurs.
- **Bouton `?`** : les descriptions textuelles longues dans les sections GAMMA GPU et MODE JEU sont remplacées par un bouton `?` circulaire — l'info s'affiche au survol ou au clic, sans encombrer le panneau.

### Amélioré
- **Mode Jeu ciblé sur l'écran du jeu** : le préréglage bri/con et la suspension DDC-CI s'appliquent désormais uniquement à l'écran contenant le jeu (détecté via `GetMonitorInfoW`). Les autres écrans restent entièrement libres pendant la session — l'utilisateur peut ajuster Discord, OBS ou tout monitoring sans attendre la fin de la partie. Fallback sur tous les écrans si la détection échoue.
- **Message DDC-CI indisponible** : la carte N/A et le banner mentionnent explicitement les écrans intégrés (laptop) comme cause normale, et rappellent que le slider γ reste disponible.

### Corrigé
- **Conflit App Rules ↔ Mode Jeu en alt-tab** : les App Rules reprenaient pendant les 2 s du timer de sortie du mode jeu, causant un flickering de luminosité à chaque alt-tab. La suppression couvre désormais toute la fenêtre de debounce (`_gaming_exit_timer.isActive()`).
- **Panneau devant les jeux fenêtrés** : masqué automatiquement à l'entrée du mode jeu pour ne pas s'afficher sur les jeux en borderless/windowed-fullscreen.

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
