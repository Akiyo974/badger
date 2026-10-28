# Changelog

Les changements notables de ce repo. Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

## Non publié

### Ajouté
- `tools/deploy.ps1` : déploie `system/` sur le badge en une commande. Il passe le badge en mode clé USB, copie seulement les fichiers dont le contenu a changé, ne touche jamais à `secrets.py`, puis redémarre le badge. Options `-DryRun`, `-Only`, `-NoReboot` et `-Port`.
- `CHANGELOG.md`.

### Modifié
- README : section déploiement, réglages et façon de travailler par pull requests.
- `.gitignore` : ignore le dossier local `.local/` (brouillons et sauvegardes).

## 2026-10-27 : version d'origine

- Copie du badge GitHub Universe '26 tel que livré (MonaOS 4.0, MicroPython 1.29) dans `system/`.
- `secrets.example.py`, `tools/make_qr.py` et les fins de ligne LF.
