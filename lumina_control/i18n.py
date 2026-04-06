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
    "Synchroniser les écrans":          "Sync screens",
    "Maître":                           "Master",
    "Gains RGB":                        "RGB gains",
    "Sync maintenant":                  "Sync now",
    "Décalages relatifs":               "Relative offsets",
    "Offset lum.":                      "Bri. offset",
    "Offset con.":                      "Con. offset",
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
    "INSTANTANÉ":                       "SNAPSHOT",
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

    # ── monitor_card ─────────────────────────────────────────────────────────
    "Écran {}":                         "Screen {}",
    "☀  Lum.":                          "☀  Bri.",
    "◑  Con.":                          "◑  Con.",
    "γ  Gamma":                         "γ  Gamma",
    "Écran {}  (N/A)":                  "Screen {}  (N/A)",

    # ── app_rules_dialog ──────────────────────────────────────────────────────
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
