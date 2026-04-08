# Dépannage

## Le moniteur n'apparaît pas dans Lumina Control

**Cause la plus fréquente** : DDC-CI désactivé dans l'OSD du moniteur.

**Solution** :
1. Ouvrir l'OSD de l'écran (bouton physique)
2. Activer DDC-CI (voir [Installation → Activer DDC-CI](Installation#activer-ddcci-sur-votre-moniteur))
3. Éteindre et rallumer le moniteur
4. Cliquer **↻** (rafraîchir) dans Lumina Control

Si le moniteur apparaît en **(N/A)**, il est détecté par Windows mais ne répond pas aux commandes DDC-CI. Certains écrans désactivent DDC-CI automatiquement après un changement de source ou une mise en veille — répéter la manipulation.

---

## Les sliders ne font rien / les valeurs ne changent pas

- **DDC-CI non supporté** par ce modèle de moniteur (rares, notamment certains écrans gaming ou bon marché)
- **Connexion incompatible** : DDC-CI nécessite une connexion **DisplayPort** ou **HDMI**. Les adaptateurs et KVM peuvent bloquer le signal DDC-CI. Les connexions **VGA** ne supportent pas DDC-CI.
- **Driver GPU** : certains drivers NVIDIA ou AMD bloquent DDC-CI sur certaines sorties. Essayer une autre sortie physique.

---

## Plusieurs moniteurs semblent décalés (mauvais moniteur contrôlé)

Lumina Control utilise `EnumDisplayMonitors` pour associer de manière stable les handles DDC-CI aux écrans physiques. Si l'ordre semble incorrect après un changement de configuration :

1. Débrancher et rebrancher les câbles
2. Relancer Lumina Control
3. Utiliser le bouton **↻** pour rafraîchir la détection

---

## La correction gamma disparaît après redémarrage

C'est le comportement normal de Windows — `SetDeviceGammaRamp` (GDI32) est remis à zéro à chaque session. Lumina Control réapplique automatiquement les valeurs sauvegardées au démarrage **si** l'option **Lancer au démarrage** est activée dans les paramètres.

---

## L'application ne démarre pas / plante au démarrage

1. Vérifier les logs dans `%APPDATA%\LuminaControl\` (si un fichier de log est présent)
2. Relancer depuis la ligne de commande pour voir les erreurs :
   ```
   "C:\Program Files\LuminaControl\LuminaControl.exe"
   ```
3. Si une autre instance est déjà en cours, elle sera réactivée automatiquement (instance unique via `QLocalServer`)

---

## L'application se lance mais l'icône n'apparaît pas dans le tray

Cliquer sur la flèche **^** dans la barre des tâches pour afficher les icônes cachées. Faire glisser l'icône Lumina vers la zone visible pour l'épingler.

---

## Le mode nuit / teinte chaude ne fonctionne pas

La teinte chaude est appliquée via la correction gamma GPU (GDI32). Elle nécessite :
- Que l'écran soit correctement détecté par Windows avec son `device_name` (`\\.\DISPLAY1` etc.)
- Que la session Windows soit active (pas de bureau verrouillé)

---

## Les règles par application ne se déclenchent pas

1. Vérifier que **Règles par app** est activé dans les paramètres
2. Vérifier que la règle concernée est bien activée (toggle vert)
3. S'assurer que le nom du processus correspond exactement (`vlc.exe`, pas `VLC.exe` — la comparaison est insensible à la casse mais le nom doit être correct)
4. Utiliser le picker **Applications en cours** pour sélectionner le processus depuis la liste plutôt que de le saisir manuellement

---

## SmartScreen bloque l'installation

C'est normal pour un logiciel récent sans historique de réputation Microsoft. Cliquer sur **Informations complémentaires → Exécuter quand même**. La réputation se construit au fil des installations.
