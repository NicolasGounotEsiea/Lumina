# Installation

## Depuis la release GitHub (recommandé)

1. Aller sur [Releases](https://github.com/NicolasGounotEsiea/Lumina/releases/latest)
2. Télécharger **LuminaControlSetup.exe**
3. Exécuter l'installeur — Windows peut afficher un avertissement SmartScreen la première fois, cliquer **Informations complémentaires → Exécuter quand même**
4. L'application se lance et s'installe dans la barre des tâches

> L'installeur crée un raccourci dans le menu Démarrer et propose d'activer le lancement au démarrage Windows.

---

## Depuis les sources

### Prérequis

- Python 3.11+
- pip

### Étapes

```bash
git clone https://github.com/NicolasGounotEsiea/Lumina.git
cd Lumina
python -m venv .venv
.venv\Scripts\activate
pip install PySide6 monitorcontrol screeninfo pywin32
python multiscreen_tray.py
```

---

## Activer DDC-CI sur votre moniteur

Lumina Control communique avec les moniteurs via le protocole **DDC-CI** (Display Data Channel Command Interface). Il doit être activé manuellement dans l'OSD de chaque écran.

La localisation du paramètre varie selon la marque :

| Marque | Chemin dans l'OSD |
|---|---|
| Dell | Menu → Others → DDC/CI |
| LG | Menu → General → DDC/CI |
| Samsung | Menu → System → PC/AV Mode ou DDC/CI |
| BenQ | Menu → System → DDC/CI |
| Asus | Menu → System Setup → DDC/CI |
| AOC | Menu → Extra → DDC/CI |

Si le moniteur n'apparaît pas dans Lumina Control après activation, éteignez-le et rallumez-le, puis relancez l'application.

---

## Désinstallation

Depuis **Paramètres Windows → Applications → Lumina Control → Désinstaller**.

Les données utilisateur (`%APPDATA%\LuminaControl\`) ne sont pas supprimées automatiquement. Pour une désinstallation complète, supprimer ce dossier manuellement.
