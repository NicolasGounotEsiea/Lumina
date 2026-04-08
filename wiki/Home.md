# Lumina Control — Wiki

Lumina Control est une application Windows de contrôle multi-écrans via DDC-CI : luminosité, contraste, correction gamma, calibrage RGB et profils par application, le tout depuis la barre des tâches, sans driver tiers.

---

## Navigation

| Page | Description |
|---|---|
| [Installation](Installation) | Installer le logiciel (release ou source) |
| [Guide utilisateur](Guide-Utilisateur) | Utilisation au quotidien |
| [Règles par application](Regles-Par-Application) | Profils automatiques selon l'app active |
| [Calibrage](Calibrage) | Calibrage RGB et assistant guidé |
| [Dépannage](Depannage) | Problèmes courants et solutions |
| [Architecture](Architecture) | Structure du code (pour les développeurs) |
| [Build & Release](Build-et-Release) | Compiler et publier une version |
| [FAQ](FAQ) | Questions fréquentes |

---

## Aperçu rapide

```
Icône tray  →  clic gauche  →  panneau principal
            →  clic droit   →  menu contextuel
```

Le panneau principal expose :
- **Luminosité globale** — slider synchronisé sur tous les écrans
- **Cartes par écran** — contrôle individuel bri/con/gamma/power
- **Sync** — mode maître/esclave avec décalage relatif optionnel
- **Règles par app** — profils automatiques (VLC, Teams, Photoshop…)
- **Profils nommés** — sauvegarde et restauration en un clic
- **Paramètres** — démarrage Windows, mode nuit, mode focus

---

## Compatibilité

- Windows 10 / 11 (64-bit)
- Écrans avec DDC-CI activé dans l'OSD (On-Screen Display) du moniteur
- Pas de driver tiers requis
