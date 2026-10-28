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

### Corrigé
- App Badge : la ligne « Last push » n'affiche plus l'activité d'un autre compte après un changement de `GITHUB_USERNAME`, et s'efface quand GitHub ne renvoie plus aucun événement.
- `deploy.ps1` : s'arrête sans redémarrer le badge si Windows n'arrive pas à finir l'écriture, au lieu d'attendre 2 s et de risquer des fichiers corrompus.
- `deploy.ps1` : ne cible que le badge (`VID_2E8A&PID_1101`), relie le port série à son lecteur par le numéro de série USB, et demande `-Port` si plusieurs badges sont branchés. Le déploiement s'arrête si le port choisi ne peut pas être relié à son lecteur.
- `deploy.ps1` : un `-Port` donné à la main n'est plus remplacé après le passage en mode clé USB.
- `deploy.ps1` : `-Only` est normalisé (`.`, `..`, barres) et doit rester dans `system/` ; avant, `-Only .` copiait `main.py` sous le nom `ain.py`.

### Sécurité
- App Contacts : les liens reçus sont vérifiés avant d'être enregistrés : LinkedIn uniquement sur `linkedin.com`, pseudo GitHub valide, site en `https://`. Les liens douteux sont retirés, mais l'échange se termine normalement des deux côtés.
- App Contacts : carnet limité à 200 contacts.

## 2026-10-27 : version d'origine

- Copie du badge GitHub Universe '26 tel que livré (MonaOS 4.0, MicroPython 1.29) dans `system/`.
- `secrets.example.py`, `tools/make_qr.py` et les fins de ligne LF.
