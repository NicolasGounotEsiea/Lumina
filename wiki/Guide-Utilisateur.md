# Guide utilisateur

## Icône tray

Lumina Control vit dans la zone de notification Windows (barre des tâches, côté droit).

| Action | Résultat |
|---|---|
| Clic gauche | Afficher / masquer le panneau principal |
| Clic droit | Ouvrir le menu contextuel |

L'icône affiche en permanence le pourcentage de luminosité globale actuel sous forme de badge.

---

## Panneau principal

### Luminosité globale

Le slider en haut du panneau ajuste la luminosité de **tous les écrans simultanément**. Les boutons **Jour** et **Nuit** appliquent des préréglages configurables (80 % / 25 % par défaut).

### Cartes moniteur

Chaque écran détecté dispose d'une carte individuelle avec :

| Contrôle | Description |
|---|---|
| **Lum.** | Luminosité DDC-CI (0–100) |
| **Con.** | Contraste DDC-CI (0–100) |
| **γ Gamma** | Correction gamma GPU via GDI32 (0.60–2.40) |
| **⚙** | Ouvrir le dialog de calibrage RGB |
| **⏻** | Mettre l'écran en veille / le réveiller |

> Les modifications sont envoyées au moniteur après **150 ms d'inactivité** sur le slider pour éviter de saturer DDC-CI.

### Synchronisation

La section **Sync** permet de lier plusieurs écrans :

- **Maître** : sélectionner l'écran de référence
- **Esclave absolu** : les autres écrans suivent exactement la valeur du maître
- **Décalage relatif** : les autres écrans suivent avec un écart fixe (ex. maître − 10)
- **Sync RGB** : synchroniser également les gains couleur

### Mode Focus

Quand le mode Focus est activé, Lumina Control détecte la fenêtre active toutes les 500 ms et **assombrit automatiquement les écrans inactifs** d'un pourcentage configurable (20 % par défaut). L'écran actif reste à sa luminosité normale.

Le mode Focus peut être activé depuis :
- La section Paramètres du panneau
- Le menu contextuel du tray

### Profils nommés

Les profils permettent de sauvegarder un état complet (luminosité + contraste + gamma par écran) et de le rappeler en un clic.

- **Sauver** : entrer un nom et valider
- **Charger** : cliquer sur le profil dans la liste
- **Supprimer** : bouton ✕ à droite du profil

Les profils sont stockés dans `%APPDATA%\LuminaControl\named_profiles.json`.

> Les boutons **Sauver l'instantané** / **Restaurer l'instantané** du menu tray opèrent sur un slot unique (rapide, sans nom).

---

## Paramètres

| Paramètre | Description |
|---|---|
| **Lancer au démarrage** | Ajoute l'application à `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (sans droits admin) |
| **Mode nuit** | Applique une teinte chaude via la correction gamma GPU |
| **Chaleur** | Intensité de la teinte chaude (0–100) |
| **Dim focus** | Pourcentage d'assombrissement des écrans inactifs en mode Focus |

---

## Mise à jour

Lumina Control vérifie automatiquement les mises à jour au démarrage (délai 3 s, non bloquant). Si une nouvelle version est disponible, une bannière discrète apparaît en haut du panneau avec un bouton **Télécharger** pointant vers la page de release GitHub.
