# Changelog

Les changements notables de ce repo. Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

## Non publié

### Ajouté
- App Contacts : champ « site web » sur la carte (`CONTACT_WEBSITE`), affiché en QR. Les badges d'origine l'ignorent, l'échange marche toujours avec eux.
- App Contacts : suppression d'un contact (↓ sur sa fiche, puis confirmation).
- `tools/export_contacts.ps1` : exporte les contacts du badge en `contacts.csv` et `contacts.vcf`.
- `tests/test_contacts_compat.py` : simule des échanges entre l'app d'origine et la version modifiée.
- App Badge : pages QR codes (site, LinkedIn, GitHub) avec ↑ / ↓ depuis la vue stats, images générées par `tools/make_qr.py`.
- App Badge : ligne « Last push » en anglais sous le nom (ex. `Last push: highlight - 1d ago`), rafraîchie à chaque ouverture et gardée en cache hors ligne.
- `tools/deploy.ps1` : déploie `system/` sur le badge en une commande. Il passe le badge en mode clé USB, copie seulement les fichiers dont le contenu a changé, ne touche jamais à `secrets.py`, puis redémarre le badge. Options `-DryRun`, `-Only`, `-NoReboot` et `-Port`.
- `CHANGELOG.md`.

### Modifié
- README : section déploiement, réglages et façon de travailler par pull requests.
- `.gitignore` : ignore le dossier local `.local/` (brouillons et sauvegardes).

### Sécurité
- App Contacts : les liens reçus sont vérifiés avant d'être enregistrés : LinkedIn uniquement sur `linkedin.com`, pseudo GitHub valide, site en `https://`. Les liens douteux sont retirés, mais l'échange se termine normalement des deux côtés.
- App Contacts : carnet limité à 200 contacts.

## 2026-10-27 : version d'origine

- Copie du badge GitHub Universe '26 tel que livré (MonaOS 4.0, MicroPython 1.29) dans `system/`.
- `secrets.example.py`, `tools/make_qr.py` et les fins de ligne LF.
