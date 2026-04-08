# Calibrage

Lumina Control propose deux outils de calibrage : le **dialog RGB** par écran et l'**assistant guidé** en 6 étapes.

---

## Dialog de calibrage RGB

Accessible via le bouton **⚙** sur chaque carte moniteur.

### Réglages disponibles

| Curseur | Code VCP | Description |
|---|---|---|
| Rouge | `0x16` | Gain canal rouge (0–100) |
| Vert | `0x18` | Gain canal vert (0–100) |
| Bleu | `0x1A` | Gain canal bleu (0–100) |

> Avant toute modification RGB, Lumina Control envoie automatiquement `VCP 0x14 → 0x0B` pour activer le **User Color Mode**. Si votre moniteur ne supporte pas ce mode, les gains RGB ne seront pas appliqués.

### Procédure recommandée

1. Afficher un fond gris neutre (50 % de luminosité)
2. Ajuster le rouge, vert et bleu jusqu'à obtenir un gris perçu comme parfaitement neutre
3. Valider — les valeurs sont sauvegardées dans le moniteur via DDC-CI

---

## Assistant de calibrage guidé

Accessible via **Calibrage guidé** dans le menu tray ou le panneau principal.

L'assistant guide en **6 étapes** :

| Étape | Objectif | Pattern utilisé |
|---|---|---|
| 1 | Point noir — vérifier l'absence de glow | Noir plein |
| 2 | Point blanc — vérifier la luminosité max | Blanc plein |
| 3 | Balance des gris — neutralité colorimétrique | Gris 50 % |
| 4 | Gamma — vérifier la courbe de ton | Damier gamma |
| 5 | Couleurs primaires — saturation et teintes | Rouge / Vert / Bleu |
| 6 | Validation finale | Mire complète |

Chaque étape affiche une **fenêtre plein écran** sur le moniteur à calibrer avec le pattern approprié.

---

## Patterns plein écran

Les patterns sont également accessibles directement via **Patterns plein écran** dans le menu tray. Disponibles :

| Pattern | Usage |
|---|---|
| Noir / Blanc | Point noir / point blanc |
| Gris 25 % / 50 % / 75 % | Niveaux intermédiaires |
| Rouge / Vert / Bleu | Calibrage couleurs primaires |
| Damier gamma | Vérification de la courbe gamma |
| Mire complète | Validation globale |

Appuyer sur **Échap** ou cliquer pour fermer le pattern.

---

## Correction gamma GPU

La correction gamma dans Lumina Control agit via `SetDeviceGammaRamp` (GDI32) — elle modifie la **table de correspondance** (LUT) de la carte graphique **indépendamment** du DDC-CI.

- Plage : **0.60** (très sombre) à **2.40** (très lumineux), neutre à **1.00**
- Elle s'applique par écran via le slider **γ Gamma** dans chaque carte
- Le slider global **GAMMA GPU** applique la même valeur à tous les écrans simultanément
- La valeur est persistée par écran dans `settings.json`

> La correction gamma GPU est réinitialisée au redémarrage de Windows (comportement normal de GDI32). Lumina Control réapplique automatiquement la valeur sauvegardée au démarrage.
