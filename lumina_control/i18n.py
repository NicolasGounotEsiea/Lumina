"""Internationalisation helper.

Usage::

    from lumina_control.i18n import _
    label = _("Luminosité globale")

French is the default/fallback language (strings are authored in French).
The system locale is detected once at import time.
"""
import locale as _locale

# ── English translations ──────────────────────────────────────────────────────
# Keys: French UI strings (the source language).
# Values: English translations.

_EN: dict[str, str] = {
    # ── tray ─────────────────────────────────────────────────────────────────
    "Afficher":                         "Show",
    "Patterns plein écran":             "Fullscreen patterns",
    "Calibrage guidé":                  "Guided calibration",
    "Mode Focus":                       "Focus mode",
    "Sauver l'instantané":              "Save snapshot",
    "Restaurer l'instantané":           "Restore snapshot",
    "Quitter":                          "Quit",

    # ── main_window ───────────────────────────────────────────────────────────
    "Luminosité globale":               "Global brightness",
    "☀  Jour  80%":                     "☀  Day  80%",
    "☾  Nuit  25%":                     "☾  Night  25%",
    "⏻  Allumer":                       "⏻  Turn on",
    "⭘  Éteindre":                      "⭘  Turn off",
    "⏵  Réveiller":                     "⏵  Wake",
    "SYNCHRONISATION":                  "SYNCHRONISATION",
    "Lier les écrans":                  "Link screens",
    "Maître":                           "Master",
    "L'écran maître pilote les autres": "The master screen controls the others",
    "Couleurs RGB":                     "RGB colors",
    "Sync maintenant":                  "Sync now",
    "Décalage permanent":               "Fixed offset",
    "Maintient un écart fixe de luminosité et contraste entre le maître et les autres écrans":
        "Keeps a fixed brightness and contrast gap between the master and the other screens",
    "Lum. secondaires":                 "Sec. bri.",
    "Con. secondaires":                 "Sec. con.",
    "Actif — {} écran(s) lié(s)":       "Active — {} screen(s) linked",
    "⚠ Suspendu — Mode Focus actif":    "⚠ Suspended — Focus mode active",
    "⚠ Suspendu — Mode Jeu actif":      "⚠ Suspended — Gaming mode active",
    "GAMMA GPU":                        "GPU GAMMA",
    "Gamma":                            "Gamma",
    "Importer":                         "Import",
    "Exporter":                         "Export",
    "Reset":                            "Reset",
    "MODE FOCUS":                       "FOCUS MODE",
    "Écran actif lumineux, autres atténués.": "Active screen bright, others dimmed.",
    "Activé":                           "On",
    "Désactivé":                        "Off",
    "Atténuation":                      "Dim amount",
    "SAUVEGARDE RAPIDE":                "QUICK SAVE",
    "Mémorise l'état actuel en 1 clic — utile avant d'expérimenter.":
        "Saves the current state in one click — useful before experimenting.",
    "Préréglages permanents nommés — luminosité, contraste et gamma par écran.":
        "Permanent named presets — brightness, contrast and gamma per screen.",
    "Sauver":                           "Save",
    "Restaurer":                        "Restore",
    "Aucun instantané":                 "No snapshot",
    "PROFILS AUTOMATIQUES":             "APP PROFILES",
    "Activer les profils par application": "Enable per-app profiles",
    "Aucune règle active":              "No active rule",
    "Gérer les règles…":                "Manage rules…",
    "OUTILS":                           "TOOLS",
    "Quitter l'application":            "Quit application",
    "Rafraîchir les écrans":            "Refresh monitors",
    "Masquer":                          "Hide",
    "ÉCRANS":                           "MONITORS",
    "Erreur lors du scan des écrans":   "Monitor scan error",
    "Instantané introuvable":           "Snapshot not found",
    "Dernier : {}":                     "Last: {}",
    "Détecté : {}":                     "Detected: {}",
    "● {}":                             "● {}",

    # ── monitor_enumerate ────────────────────────────────────────────────────
    "Écran détecté":                    "Monitor detected",
    "Gauche":                           "Left",
    "Droite":                           "Right",
    "Centre":                           "Centre",
    "Haut":                             "Top",
    "Bas":                              "Bottom",
    "Principal":                        "Primary",

    # ── monitor_card — write warning ─────────────────────────────────────────
    "⚠  Réglages sans effet — le moniteur refuse les commandes DDC-CI.\n"
    "Cause probable : un preset image (Game / FPS / Cinema) est actif dans l'OSD.\n"
    "Appuyez sur le bouton physique du moniteur → Menu Image → choisissez le mode Utilisateur ou Standard.":
        "⚠  Settings have no effect — the monitor is rejecting DDC-CI commands.\n"
        "Likely cause: a picture preset (Game / FPS / Cinema) is active in the OSD.\n"
        "Press the physical button on your monitor → Picture menu → select User or Standard mode.",

    # ── monitor_card ─────────────────────────────────────────────────────────
    "Les écrans intégrés (laptop) ne supportent pas DDC-CI. "
    "Pour un écran externe : activez « DDC/CI » dans le menu OSD (boutons physiques) puis cliquez ↻.\n"
    "Le slider γ Gamma reste disponible sur tous les écrans.":
        "Built-in screens (laptop) do not support DDC-CI. "
        "For an external monitor: enable « DDC/CI » in the OSD menu (physical buttons) then click ↻.\n"
        "The γ Gamma slider remains available on all screens.",
    "{} écran(s) sans DDC-CI — écran intégré (laptop) ou DDC/CI désactivé dans le menu OSD du moniteur.":
        "{} monitor(s) without DDC-CI — built-in screen (laptop) or DDC/CI disabled in the monitor OSD.",
    "Écran {}":                         "Screen {}",
    "☀  Lum.":                          "☀  Bri.",
    "◑  Con.":                          "◑  Con.",
    "γ  Gamma":                         "γ  Gamma",
    "Écran {}  (N/A)":                  "Screen {}  (N/A)",
    "Ajuste la luminosité perçue des tons intermédiaires via la carte graphique.\n"
    "Fonctionne même si le DDC-CI est indisponible.\n"
    "1.00 = neutre  ·  < 1.00 = plus sombre  ·  > 1.00 = plus clair\n"
    "Pour un réglage global (tous les écrans), voir la section « GAMMA GPU ».":
        "Adjusts the perceived brightness of mid-tones via the graphics card.\n"
        "Works even if DDC-CI is unavailable.\n"
        "1.00 = neutral  ·  < 1.00 = darker  ·  > 1.00 = brighter\n"
        "For a global setting (all monitors), see the « GPU GAMMA » section.",

    # ── app_rules_dialog ──────────────────────────────────────────────────────
    "Profils automatiques par application": "Automatic per-app profiles",
    "Détection automatique toutes les 500 ms · "
    "Les réglages sont restaurés dès que vous quittez l'application.":
        "Automatic detection every 500 ms · "
        "Settings are restored as soon as you leave the application.",
    "Lum: {}%":                         "Bri: {}%",
    "Con: {}%":                         "Con: {}%",
    "γ: {}":                            "γ: {}",
    "RVB: {}/{}/{}":                    "RGB: {}/{}/{}",
    "Activer / désactiver":             "Enable / disable",
    "Modifier":                         "Edit",
    "Supprimer":                        "Delete",
    "Modifier la règle":                "Edit rule",
    "Nouvelle règle":                   "New rule",
    "Actif maintenant :":               "Active now:",
    "Utiliser":                         "Use",
    "Applications en cours d'exécution": "Running applications",
    "— choisir une app —":              "— select an app —",
    "Actualiser la liste des applications": "Refresh app list",
    "Nom de l'exécutable (ex: vlc.exe)": "Executable name (e.g. vlc.exe)",
    "ex. vlc.exe":                      "e.g. vlc.exe",
    "Nom affiché":                      "Display name",
    "ex. VLC, Zoom, Photoshop…":        "e.g. VLC, Zoom, Photoshop…",
    "Luminosité":                       "Brightness",
    "Contraste":                        "Contrast",
    "Gamma GPU":                        "GPU Gamma",
    "Colorimétrie  —  Gains RVB":       "Colorimetry  —  RGB Gains",
    "Ajuste les canaux R/V/B indépendamment via DDC-CI  "
        "(nécessite le support Gains utilisateur sur le moniteur).":
        "Adjusts R/G/B channels independently via DDC-CI "
        "(requires User Gain support on the monitor).",
    "Ne pas modifier les gains RVB":    "Do not modify RGB gains",
    "Rouge":                            "Red",
    "Vert":                             "Green",
    "Bleu":                             "Blue",
    "Aperçu :":                         "Preview:",
    "Annuler":                          "Cancel",
    "Enregistrer":                      "Save",
    "Profils par application":          "App profiles",
    "Aucun profil configuré.\nCliquez sur  +  pour ajouter.":
        "No profiles configured.\nClick  +  to add.",
    "Ajouter une règle":                "Add rule",
    "Rétablir les défauts":             "Reset to defaults",
    "Fermer":                           "Close",
    "Ne pas modifier":                  "Do not change",
    "Détection inactive — activez les profils dans la fenêtre principale.":
        "Detection inactive — enable profiles in the main window.",
    "App en focus :":                   "Focused app:",
    "Aucun processus détecté":          "No process detected",

    # ── startup / updater ────────────────────────────────────────────────────
    "PARAMÈTRES":                       "SETTINGS",
    "Lancer au démarrage de Windows":   "Launch at Windows startup",
    "Mise à jour disponible : {}":      "Update available: {}",
    "Télécharger":                      "Download",

    # ── named profiles ───────────────────────────────────────────────────────
    "PROFILS NOMMÉS":                   "NAMED PROFILES",
    "Nom du profil":                    "Profile name",
    "Sauver le profil":                 "Save profile",
    "Charger":                          "Load",
    "Aucun profil sauvegardé":          "No saved profiles",

    # ── onboarding ───────────────────────────────────────────────────────────
    "Bienvenue dans Lumina Control":    "Welcome to Lumina Control",
    "Contrôlez la luminosité, le contraste et la colorimétrie "
    "de vos écrans directement depuis la barre des tâches — "
    "sans driver tiers, via le protocole DDC-CI.\n\n"
    "Cet assistant va vérifier la compatibilité de vos écrans "
    "et vous présenter les fonctionnalités clés.":
        "Control the brightness, contrast and colorimetry of your monitors "
        "directly from the taskbar — no third-party driver, via the DDC-CI protocol.\n\n"
        "This wizard will check your monitor compatibility "
        "and walk you through the key features.",
    "Détection DDC-CI":                 "DDC-CI Detection",
    "DDC-CI est le protocole qui permet de contrôler vos écrans. "
    "Il doit être activé dans le menu OSD (boutons physiques) de chaque moniteur.":
        "DDC-CI is the protocol used to control your monitors. "
        "It must be enabled in the OSD menu (physical buttons) of each monitor.",
    "Scan en cours…":                   "Scanning…",
    "Si un écran est marqué indisponible :\n"
    "  1. Appuyez sur le bouton physique de votre moniteur\n"
    "  2. Cherchez « DDC/CI » dans le menu et activez-le\n"
    "  3. Rafraîchissez les écrans depuis le panneau principal":
        "If a monitor is marked unavailable:\n"
        "  1. Press the physical button on your monitor\n"
        "  2. Find « DDC/CI » in the menu and enable it\n"
        "  3. Refresh monitors from the main panel",
    "Fonctionnalités clés":             "Key features",
    "Contrôlez chaque écran individuellement ou synchronisez-les en maître/esclave avec décalages relatifs.":
        "Control each monitor individually or sync them in master/slave mode with relative offsets.",
    "Préréglage automatique dès qu'une application spécifique est au premier plan — luminosité, contraste, gamma, gains RGB.":
        "Automatic preset when a specific application is in focus — brightness, contrast, gamma, RGB gains.",
    "Détection automatique du plein écran : préréglage appliqué et écritures DDC-CI suspendues pour ne pas interrompre le jeu.":
        "Automatic fullscreen detection: preset applied and DDC-CI writes suspended to avoid interrupting the game.",
    "Tout est prêt !":                  "All set!",
    "Lumina Control est actif dans la barre des tâches.\n"
    "Cliquez sur l'icône pour ouvrir le panneau de contrôle.\n\n"
    "Vous pouvez relancer cet assistant à tout moment depuis\n"
    "la section Paramètres du panneau.":
        "Lumina Control is active in the taskbar.\n"
        "Click the icon to open the control panel.\n\n"
        "You can relaunch this wizard at any time from\n"
        "the Settings section of the panel.",
    "Aucun écran détecté.":             "No monitors detected.",
    "{} écran(s) détecté(s) :":         "{} monitor(s) detected:",
    "DDC-CI indisponible":              "DDC-CI unavailable",
    "Scan impossible : {}":             "Scan failed: {}",
    "Assistant de démarrage…":          "Setup wizard…",

    # ── onboarding — new pages ────────────────────────────────────────────────
    "🖥  Multi-écrans":                  "🖥  Multi-monitor",
    "🎮  Mode Jeu":                      "🎮  Gaming mode",
    "🌙  Mode Nuit":                     "🌙  Night mode",
    "💡  Vous pouvez relancer ce scan à tout moment via le bouton ↻ "
    "en haut du panneau principal.":
        "💡  You can re-run this scan at any time using the ↻ button "
        "at the top of the main panel.",
    "Contrôle des écrans":              "Screen control",
    "Les réglages s'appliquent en temps réel via DDC-CI — sans logiciel de pilote tiers.":
        "Settings apply in real time via DDC-CI — no third-party driver needed.",
    "Luminosité & contraste globaux":   "Global brightness & contrast",
    "Un slider unique ajuste tous vos écrans en même temps. "
    "Les préréglages Jour (80 %) et Nuit (25 %) sont accessibles en un clic.":
        "A single slider adjusts all your monitors at once. "
        "Day (80%) and Night (25%) presets are one click away.",
    "Synchronisation maître / esclave": "Master / slave synchronisation",
    "Liez vos écrans : le maître pilote les autres en absolu ou avec un décalage fixe "
    "(ex. écran secondaire toujours 10 % moins lumineux).":
        "Link your monitors: the master drives the others absolutely or with a fixed offset "
        "(e.g. secondary screen always 10% dimmer).",
    "Mode Focus":                       "Focus mode",
    "L'écran actif reste à pleine luminosité ; les autres sont atténués du niveau "
    "que vous choisissez. Utile pour se concentrer sur une seule fenêtre.":
        "The active screen stays at full brightness; others are dimmed by the amount you choose. "
        "Useful for focusing on a single window.",
    "Mode Nuit":                        "Night mode",
    "Applique une teinte chaude (GPU) sur tous vos écrans pour réduire la lumière bleue "
    "en soirée. Intensité réglable de 0 à 100 %.":
        "Applies a warm GPU tint to all your monitors to reduce blue light in the evening. "
        "Adjustable intensity from 0 to 100%.",
    "Fonctions avancées":               "Advanced features",
    "Des outils pour les utilisateurs exigeants et les configurations multi-écrans complexes.":
        "Tools for power users and complex multi-monitor setups.",
    "Détection automatique du plein écran : un préréglage de luminosité/contraste "
    "est appliqué à l'entrée, et les écritures DDC-CI sont suspendues pour ne pas "
    "interrompre le jeu. Tout est restauré à la sortie.":
        "Automatic fullscreen detection: a brightness/contrast preset is applied on entry, "
        "and DDC-CI writes are suspended to avoid interrupting the game. "
        "Everything is restored on exit.",
    "Associez un préréglage (luminosité, contraste, gamma, gains RGB) à un exécutable. "
    "Lumina Control détecte automatiquement l'application au premier plan et "
    "applique les réglages — puis les restaure dès que vous changez d'application.":
        "Assign a preset (brightness, contrast, gamma, RGB gains) to an executable. "
        "Lumina Control automatically detects the foreground application and applies "
        "the settings — then restores them when you switch apps.",
    "Profils nommés":                   "Named profiles",
    "Sauvegardez l'état complet de tous vos écrans (luminosité, contraste, gamma) "
    "sous un nom personnalisé, et rechargez-le en un clic. "
    "Idéal pour alterner entre une configuration \"Travail\" et \"Cinéma\".":
        "Save the complete state of all your monitors (brightness, contrast, gamma) "
        "under a custom name and reload it with one click. "
        "Ideal for switching between \"Work\" and \"Cinema\" configurations.",
    "Sauvegarde rapide":                "Quick save",
    "Mémorisez l'état actuel en un clic avant d'expérimenter, "
    "et restaurez-le instantanément si le résultat ne vous convient pas.":
        "Save the current state in one click before experimenting, "
        "and restore it instantly if the result isn't what you wanted.",
    "Calibrage RGB & Gamma GPU":        "RGB calibration & GPU gamma",
    "Ajustez finement les gains Rouge / Vert / Bleu via DDC-CI pour corriger les "
    "dominantes de couleur. Le gamma GPU (GDI32) agit indépendamment du DDC-CI "
    "et s'applique même si votre moniteur ne supporte pas DDC.":
        "Fine-tune Red / Green / Blue gains via DDC-CI to correct colour casts. "
        "GPU gamma (GDI32) works independently of DDC-CI "
        "and applies even if your monitor doesn't support DDC.",
    "Rappel — où trouver chaque fonction": "Quick reference — where to find each feature",
    "☀  Luminosité globale    → barre en haut du panneau":
        "☀  Global brightness     → bar at the top of the panel",
    "🔗  Synchronisation       → section SYNCHRONISATION":
        "🔗  Sync                  → SYNCHRONISATION section",
    "🎯  Mode Focus            → section MODE FOCUS":
        "🎯  Focus mode            → FOCUS MODE section",
    "🌙  Mode Nuit             → section PARAMÈTRES":
        "🌙  Night mode            → SETTINGS section",
    "🎮  Mode Jeu              → section MODE JEU":
        "🎮  Gaming mode           → GAMING MODE section",
    "⚙  Profils par app       → section PROFILS AUTOMATIQUES":
        "⚙  Per-app profiles      → APP PROFILES section",
    "📁  Profils nommés        → section PROFILS NOMMÉS":
        "📁  Named profiles        → NAMED PROFILES section",
    "🎨  Calibrage             → bouton ⚙ sur chaque écran":
        "🎨  Calibration           → ⚙ button on each monitor card",

    # ── mode priority tooltips ───────────────────────────────────────────────
    "Suspendu automatiquement quand le Mode Jeu détecte un plein écran.":
        "Automatically suspended when Gaming mode detects a fullscreen app.",
    "Priorité maximale : suspend le Mode Focus et les Profils Automatiques dès qu'un jeu passe en plein écran.":
        "Highest priority: suspends Focus mode and App Profiles as soon as a game goes fullscreen.",

    "Applique un gamma identique à tous les écrans via la carte graphique. "
    "Pour régler chaque écran indépendamment, utilisez le slider γ sur sa carte.":
        "Applies the same gamma to all monitors via the graphics card. "
        "To adjust each monitor independently, use the γ slider on its card.",

    # ── gaming mode ──────────────────────────────────────────────────────────
    "Détecte le plein écran → applique le préréglage sur l'écran du jeu → "
    "suspend le DDC-CI de cet écran pour éviter tout artefact visuel. "
    "Les autres écrans restent librement ajustables. Tout est restauré à la sortie.":
        "Detects fullscreen → applies preset to the game screen → "
        "suspends DDC-CI on that screen to avoid visual artefacts. "
        "Other screens remain freely adjustable. Everything is restored on exit.",
    "Mode Jeu":                         "Gaming mode",
    "MODE JEU":                         "GAMING MODE",
    "Préréglage auto quand un jeu est en plein écran.":
        "Auto preset when a game goes fullscreen.",
    "Lum. jeu":                         "Game bri.",
    "Con. jeu":                         "Game con.",
    "Désactivé pendant le mode jeu":    "Disabled during gaming mode",
    "Exclusions":                       "Exclusions",
    "Processus qui ne déclenchent jamais le mode jeu (ex : afterfx.exe, resolve.exe)":
        "Processes that never trigger gaming mode (e.g. afterfx.exe, resolve.exe)",

    # ── focus mode — delay ────────────────────────────────────────────────────
    "Délai Focus":                      "Focus delay",
    "Délai avant d'atténuer les écrans inactifs — évite le flickering lors d'un Alt+Tab rapide.":
        "Delay before dimming inactive screens — avoids flickering on rapid Alt+Tab.",

    # ── group separators ─────────────────────────────────────────────────────
    "RÉGLAGES":                         "SETTINGS",
    "AUTOMATISATION":                   "AUTOMATION",
    "APPLICATION":                      "APPLICATION",

    # ── circadian brightness ─────────────────────────────────────────────────
    "LUMINOSITÉ CIRCADIENNE":           "CIRCADIAN BRIGHTNESS",
    "Suit le soleil — luminosité automatique lever/coucher.":
        "Follows the sun — automatic sunrise/sunset brightness.",
    "La luminosité suit une courbe cosinus entre le lever et le coucher du soleil, "
    "avec un pic au zénith.\n\n"
    "Avant le lever et après le coucher : luminosité minimale.\n"
    "Compatible avec le Mode Focus (atténue les écrans inactifs par rapport à la cible).\n"
    "Suspendu automatiquement en Mode Jeu.":
        "Brightness follows a cosine curve between sunrise and sunset, "
        "peaking at solar noon.\n\n"
        "Before sunrise and after sunset: minimum brightness.\n"
        "Compatible with Focus mode (dims inactive screens relative to the target).\n"
        "Automatically suspended in Gaming mode.",
    "Ville":                            "City",
    "Latitude":                         "Latitude",
    "Longitude":                        "Longitude",
    "Lum. min":                         "Bri. min",
    "Lum. max":                         "Bri. max",
    "Cible actuelle : {}%":             "Current target: {}%",
    "Cible : {}%  ·  chaleur {}%":      "Target: {}%  ·  warmth {}%",
    "Paris":                            "Paris",
    "Londres":                          "London",
    "Berlin":                           "Berlin",
    "Madrid":                           "Madrid",
    "Rome":                             "Rome",
    "Amsterdam":                        "Amsterdam",
    "Bruxelles":                        "Brussels",
    "Zurich":                           "Zurich",
    "New York":                         "New York",
    "Los Angeles":                      "Los Angeles",
    "Chicago":                          "Chicago",
    "Toronto":                          "Toronto",
    "Montréal":                         "Montreal",
    "Tokyo":                            "Tokyo",
    "Seoul":                            "Seoul",
    "Sydney":                           "Sydney",
    "Dubaï":                            "Dubai",
    "Singapore":                        "Singapore",
    "São Paulo":                        "São Paulo",
    "Personnalisé":                     "Custom",
    "Chaleur circadienne":              "Circadian warmth",
    "Chaleur max":                      "Max warmth",

    # ── night mode ───────────────────────────────────────────────────────────
    "MODE NUIT":                        "NIGHT MODE",
    "Activer le mode nuit":             "Enable night mode",
    "Chaleur":                          "Warmth",

    # ── calibration ──────────────────────────────────────────────────────────
    "Calibrage RGB":                    "RGB Calibration",
    "Calibrage : {}":                   "Calibration: {}",
    "Ajustement fin des gains RGB (si supporté par l'écran).":
        "Fine-tune RGB gains (if supported by the monitor).",
    "Lier R/G/B":                       "Link R/G/B",
    "Recharger":                        "Reload",
    "Gain global":                      "Global gain",
    "Fermer":                           "Close",
    "Afficher le pattern":              "Show pattern",
    "Masquer le pattern":               "Hide pattern",
    "Écran cible":                      "Target screen",

    # Calibration wizard step titles
    "Uniformité Blanc":                 "White uniformity",
    "Uniformité Gris 50%":              "50% Gray uniformity",
    "Uniformité Noir":                  "Black uniformity",
    "Gradient Horizontal":              "Horizontal gradient",
    "Gamma Steps":                      "Gamma steps",
    "Sharpness":                        "Sharpness",

    # Calibration wizard step help texts
    "Vérifier les zones plus sombres ou jaunâtres sur fond blanc.":
        "Check for darker or yellowish areas on white background.",
    "Détecter les dominantes de couleur sur gris neutre.":
        "Detect colour casts on neutral grey.",
    "Observer les fuites de lumière (backlight bleeding).":
        "Observe light leakage (backlight bleeding).",
    "Vérifier les bandes et la linéarité de la gradation.":
        "Check banding and gradation linearity.",
    "Vérifier la progressivité des niveaux de gris.":
        "Check grey level progression.",
    "Vérifier la netteté et la sur-accentuation.":
        "Check sharpness and over-sharpening.",

    # Calibration wizard navigation
    "Étape {} / {}":                    "Step {} / {}",
    "Précédent":                        "Previous",
    "Suivant":                          "Next",
    "Terminer":                         "Finish",
}


# ── Language detection ────────────────────────────────────────────────────────

def _detect_lang() -> str:
    try:
        loc = _locale.getdefaultlocale()[0] or ""
        return "fr" if loc.lower().startswith("fr") else "en"
    except Exception:
        return "fr"


_LANG = _detect_lang()


def _(text: str) -> str:
    """Return the localised version of *text* (French source → current language)."""
    if _LANG == "fr":
        return text
    return _EN.get(text, text)
