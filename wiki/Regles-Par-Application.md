# Règles par application

Les règles par application permettent d'appliquer automatiquement un profil d'affichage dès qu'une application donnée prend le focus — et de le retirer quand elle le perd.

---

## Fonctionnement

Lumina Control surveille la **fenêtre active** toutes les **500 ms**. Quand le processus en focus correspond à une règle activée :

1. La règle est appliquée **uniquement sur l'écran contenant la fenêtre** (`MonitorFromWindow`)
2. Les paramètres non renseignés dans la règle (valeur `—`) sont ignorés
3. À la perte de focus, les valeurs précédentes sont restaurées

> La détection utilise une garde de stabilité : la règle ne se déclenche que si le même processus est actif pendant au moins 500 ms consécutives, évitant les flashs lors d'un Alt+Tab rapide.

---

## Règles par défaut

L'application est livrée avec des règles préconfigurées :

| Application | Luminosité | Contraste | Gamma |
|---|---|---|---|
| VLC / mpv / MPC-HC / MPC-BE | 25 % | 50 % | — |
| Microsoft Teams / Zoom / Webex | 90 % | 60 % | — |
| Photoshop / Lightroom | 70-75 % | 55 % | 1.00 |
| Blender / Steam / OBS | 80 % | 55-65 % | — |
| Discord | 65 % | — | — |

---

## Créer ou modifier une règle

1. Ouvrir le panneau principal → section **Règles par app**
2. Cliquer **+ Ajouter**
3. Sélectionner un processus dans la liste des applications en cours **ou** saisir manuellement le nom de l'exécutable (ex. `vlc.exe`)
4. Renseigner les valeurs souhaitées — laisser `—` pour ne pas modifier un paramètre
5. Valider

### Paramètres disponibles par règle

| Champ | Plage | Description |
|---|---|---|
| **Luminosité** | 0–100 | Brightness DDC-CI (VCP `0x10`) |
| **Contraste** | 0–100 | Contrast DDC-CI (VCP `0x12`) |
| **Gamma** | 0.60–2.40 | Correction GPU via GDI32 |
| **Rouge** | 0–100 | Gain rouge DDC-CI (VCP `0x16`) |
| **Vert** | 0–100 | Gain vert DDC-CI (VCP `0x18`) |
| **Bleu** | 0–100 | Gain bleu DDC-CI (VCP `0x1A`) |

Les gains RGB sont appliqués en mode **User Color** (VCP `0x14 → 0x0B`) — certains moniteurs ne supportent pas ce mode.

---

## Activer / désactiver

- **Globalement** : checkbox **Règles par app** dans la section Paramètres
- **Par règle** : toggle activé/désactivé à droite de chaque règle dans la liste

---

## Persistance

Les règles sont sauvegardées dans :

```
%APPDATA%\LuminaControl\app_rules.json
```

Format JSON, éditable manuellement si nécessaire.

```json
[
  {
    "process": "vlc.exe",
    "label": "VLC",
    "brightness": 25,
    "contrast": 50,
    "gamma": null,
    "red": null,
    "green": null,
    "blue": null,
    "enabled": true
  }
]
```
