# badger

Mes modifications du badge **GitHub Universe '26** (Badger 2350 : RP2350, écran 320×240, MonaOS 4.0, MicroPython).

## Contenu

| Dossier | Rôle |
|---|---|
| `system/` | Copie exacte du lecteur USB du badge (`/system` sur l'appareil) : `main.py`, l'animation de démarrage, les apps et les assets |
| `tools/` | Scripts à lancer sur le PC : déploiement, génération des QR codes |
| `secrets.example.py` | Modèle des réglages ; le vrai `secrets.py` n'est jamais commité |
| `CHANGELOG.md` | Historique des changements |

## Déployer sur le badge

Branche le badge en USB, puis depuis la racine du repo :

```powershell
./tools/deploy.ps1
```

Le script :
1. trouve le badge (port série et lecteur **BADGER**) et le passe tout seul en mode clé USB si besoin ;
2. copie uniquement les fichiers dont le **contenu** a changé (la date ne compte pas, git la modifie à chaque checkout) ;
3. ne touche jamais à `secrets.py` et ne supprime rien sur le badge ;
4. redémarre le badge en mode normal.

| Option | Effet |
|---|---|
| `-DryRun` | Liste les fichiers qui seraient copiés, sans rien écrire |
| `-Only apps/badge` | Ne déploie qu'un sous-dossier de `system/` |
| `-NoReboot` | Laisse le badge en mode clé USB après la copie |
| `-Port COM4` | Force le port série si la détection échoue |

Pour tester une pull request : `git checkout <branche>` puis `./tools/deploy.ps1`.

### À la main

1. Mettre le badge en mode clé USB (app **Mass Storage**, ou deux appuis rapides sur RESET).
2. Copier le contenu de `system/` sur le lecteur **BADGER**.
3. Éjecter le lecteur, puis redémarrer le badge.

## Exporter les contacts

```powershell
./tools/export_contacts.ps1 -OutDir ~/Desktop
```

Lit les cartes échangées avec l'app **Contacts** (dans `/state`, hors du lecteur USB) et écrit `contacts.csv` et `contacts.vcf`, à importer dans un téléphone, Outlook ou Google Contacts.

## Tests

```powershell
py tests/test_contacts_compat.py
```

Simule des échanges de cartes entre l'app Contacts d'origine (lue depuis le premier commit) et la version de ce repo, pour vérifier qu'on peut toujours échanger avec un badge non modifié.

## Réglages

Utiliser l'app **Settings** du badge, ou copier `secrets.example.py` en `secrets.py` sur le lecteur et le remplir.

## Façon de travailler

- `main` reste déployable à tout moment.
- Chaque amélioration passe par une branche (`feat/…`, `fix/…`) et une pull request, testée sur le badge avec `deploy.ps1` avant le merge.
- Chaque PR ajoute sa ligne dans `CHANGELOG.md`, sous « Non publié ».

## Bon à savoir

- `/system` est en lecture seule pour le badge : on le modifie uniquement par le lecteur USB.
- Les caches et sauvegardes (stats GitHub, succès, contacts…) vivent dans `/state`, hors du lecteur USB.
- Console MicroPython sur le port série du badge (115200 bauds), par exemple avec Thonny.
