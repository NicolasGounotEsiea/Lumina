# Build & Release

## Prérequis

- Python 3.11+
- [PyInstaller](https://pyinstaller.org/) : `pip install pyinstaller`
- [ImageMagick](https://imagemagick.org/) : conversion PNG → ICO
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) installé dans `C:\Program Files (x86)\Inno Setup 6\`

## Build local

```powershell
.\build.ps1
```

Produit : `dist-installer\LuminaControlSetup.exe`

Le script enchaîne :
1. Conversion `icon.png` → `icon.ico` via ImageMagick (multi-résolutions : 16, 32, 48, 256 px)
2. `pyinstaller LuminaControl.spec --noconfirm`
3. `ISCC.exe installer.iss`

---

## CI/CD (GitHub Actions)

Le workflow `.github/workflows/ci.yml` se déclenche sur chaque push (`main` ou tag `v*`) et PR.

### Jobs

```
push → lint → build → release (tags v* uniquement)
```

| Job | Description |
|---|---|
| **lint** | `ast.parse` sur tous les `.py` + `pyflakes lumina_control/` |
| **build** | PyInstaller → Inno Setup → artifact `LuminaControlSetup` |
| **release** | Vérifie le tag vs `AppVersion` dans `installer.iss`, atteste la provenance, crée la GitHub Release avec les notes extraites du CHANGELOG |

### Attestation de provenance

Le job `release` génère une **attestation SLSA** via `actions/attest-build-provenance`. Elle prouve cryptographiquement que le `.exe` a été produit par ce workflow exact. Vérifiable avec :

```bash
gh attestation verify LuminaControlSetup.exe --repo NicolasGounotEsiea/Lumina
```

---

## Publier une nouvelle version

### 1. Mettre à jour la version

Dans `lumina_control/config.py` :
```python
APP_VERSION = "1.3.0"
```

Dans `installer.iss` :
```ini
AppVersion=1.3.0
```

### 2. Mettre à jour le CHANGELOG

Ajouter une section `## [1.3.0] — YYYY-MM-DD` dans `CHANGELOG.md` avec les ajouts, améliorations et correctifs.

### 3. Committer, tagger, pousser

```bash
git add lumina_control/config.py installer.iss CHANGELOG.md
git commit -m "chore: bump version to 1.3.0"
git tag v1.3.0
git push origin main --tags
```

La CI se déclenche automatiquement, build le `.exe`, l'atteste et crée la release GitHub avec les notes du CHANGELOG.

### Vérifications avant release

- [ ] `AppVersion` dans `installer.iss` correspond au tag (la CI le vérifie et échoue sinon)
- [ ] Section correspondante présente dans `CHANGELOG.md` (la CI l'extrait pour les release notes)
- [ ] Pyflakes propre (la CI lint avant de builder)

---

## Structure du spec PyInstaller

`LuminaControl.spec` configure :
- Point d'entrée : `multiscreen_tray.py`
- Données bundlées : `icon.png`
- Hidden imports : tous les sous-modules `lumina_control.*` + pywin32 + stdlib nécessaires
- Mode console désactivé (`console=False`)
- UPX activé pour réduire la taille du `.exe`
- Icône : `icon.ico`
