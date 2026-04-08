# FAQ

## Lumina Control est-il gratuit ?

Lumina Control est un logiciel propriétaire. Consulter la page [Releases](https://github.com/NicolasGounotEsiea/Lumina/releases) pour les conditions de distribution.

---

## Faut-il installer un driver ?

Non. Lumina Control utilise uniquement des APIs Windows standard :
- **DDC-CI** via la bibliothèque `monitorcontrol` (communication I2C native)
- **Gamma GPU** via `SetDeviceGammaRamp` (GDI32, intégré à Windows)
- **Détection fenêtre active** via `win32api` (pywin32)

Aucun driver tiers, aucune modification système requise.

---

## Pourquoi mon écran n'est-il pas détecté ?

DDC-CI doit être activé dans l'OSD du moniteur. Voir [Dépannage](Depannage) pour la procédure par marque.

---

## La luminosité change-t-elle instantanément ?

Les commandes DDC-CI sont envoyées après **150 ms** d'inactivité sur le slider (debounce). La réponse du moniteur varie selon le modèle : de presque instantanée à 1-2 secondes pour certains écrans anciens.

---

## Lumina Control consomme-t-il des ressources ?

Très peu. L'application est entièrement événementielle. Le seul polling actif est :
- Détection de la fenêtre active : **toutes les 500 ms** (uniquement si les règles par app ou le mode Focus sont activés)
- Vérification de mise à jour : **une seule fois** au démarrage, avec un délai de 3 s, sur un thread dédié

---

## Les réglages sont-ils sauvegardés sur le moniteur ou dans l'application ?

Les deux :
- **Luminosité et contraste DDC-CI** : écrits dans le moniteur lui-même, persistent même sans Lumina Control
- **Gamma GPU** : sauvegardé par Lumina Control dans `settings.json`, réappliqué au démarrage
- **Profils et règles** : stockés dans `%APPDATA%\LuminaControl\`

---

## Puis-je utiliser Lumina Control avec un KVM ou un hub USB-C ?

Ça dépend du KVM/hub. Beaucoup bloquent le signal DDC-CI. Si l'écran n'est pas détecté en passant par un KVM, essayer une connexion directe pour vérifier si le moniteur supporte bien DDC-CI.

---

## La fenêtre principale apparaît-elle dans Alt+Tab ?

Oui, depuis la version 1.2.0 (suppression du flag `Qt.Tool` pour permettre la mise à jour de l'icône dans la barre des tâches). Cliquer sur **✕** la ferme dans le tray sans quitter l'application.

---

## Comment vérifier l'authenticité du fichier téléchargé ?

Chaque release est accompagnée d'une **attestation de provenance SLSA** générée par GitHub Actions. Pour vérifier :

```bash
gh attestation verify LuminaControlSetup.exe --repo NicolasGounotEsiea/Lumina
```

Requiert le [GitHub CLI](https://cli.github.com/).

---

## Comment réinitialiser tous les paramètres ?

Supprimer le dossier `%APPDATA%\LuminaControl\`. Au prochain démarrage, les valeurs par défaut et les règles par application pré-configurées seront restaurées.

---

## L'application peut-elle contrôler la luminosité des écrans d'ordinateurs portables ?

Non. Les écrans intégrés (laptop) utilisent une interface différente (ACPI/WMI), pas DDC-CI. Lumina Control est conçu pour les moniteurs externes.
