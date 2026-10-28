# badger

Mes modifications du badge **GitHub Universe '26** (Badger 2350 : RP2350, écran 320×240, MonaOS 4.0, MicroPython).

<p align="center">
  <img src="docs/screenshots/menu.png" width="320" alt="Menu MonaOS">
  <img src="docs/screenshots/badge.png" width="320" alt="App Badge : stats GitHub">
</p>

## Galerie

Captures prises directement sur le badge avec `tools/screenshot.ps1`.

### Apps modifiées dans ce repo

| Badge | Badge : QR codes | Contacts |
|---|---|---|
| ![Badge](docs/screenshots/badge.png) | ![QR du site](docs/screenshots/badge-qr.png) | ![Contacts](docs/screenshots/contacts.png) |
| **Radar** | **Radar : liste** | |
| ![Radar](docs/screenshots/radar.png) | ![Liste du Radar](docs/screenshots/radar-list.png) | |

Les badges du Radar sur ces captures sont simulés (je n'ai qu'un badge).

### Apps d'origine

| Menu | Snake | Pong |
|---|---|---|
| ![Menu](docs/screenshots/menu.png) | ![Snake](docs/screenshots/snake.png) | ![Pong](docs/screenshots/pong.png) |
| **Merge Conflict** | **Flappy Mona** | **Mona Pet** |
| ![Merge Conflict](docs/screenshots/merge_conflict.png) | ![Flappy Mona](docs/screenshots/flappy_mona.png) | ![Mona Pet](docs/screenshots/mona_pet.png) |
| **Mona Paint** | **Rogue** | **Brattal** |
| ![Mona Paint](docs/screenshots/mona_paint.png) | ![Rogue](docs/screenshots/rogue.png) | ![Brattal](docs/screenshots/brattal.png) |
| **Life** | **ISS** | |
| ![Life](docs/screenshots/life.png) | ![ISS](docs/screenshots/iss.png) | |

## Contenu

| Dossier | Rôle |
|---|---|
| `system/` | Copie exacte du lecteur USB du badge (`/system` sur l'appareil) : `main.py`, l'animation de démarrage, les apps et les assets |
| `tools/` | Scripts à lancer sur le PC : déploiement, captures d'écran, export des contacts, QR codes |
| `docs/screenshots/` | Captures du README et leur liste (`captures.json`) |
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

## Apps ajoutées ou modifiées

| App | Ce qui change |
|---|---|
| **Badge** | Pages QR codes (↑ / ↓) et ligne « Last push » sous le nom |
| **Contacts** | Liens reçus vérifiés, champ site web, suppression, export vers le PC |
| **Radar** (nouvelle) | Les badges autour de toi, placés selon leur distance, avec leur nom et leur statut |

### Radar

- **Distance seulement** : le Bluetooth donne la force du signal, pas la direction. Plus un badge est près du centre, plus il est proche ; son angle est juste une place fixe tirée de son identifiant.
- **Badges visibles** : tous les badges qui ont Radar ouvert, et les badges d'origine pendant qu'ils sont dans Contacts, Pong ou Merge Conflict (leur Bluetooth ne s'annonce qu'à ce moment-là).
- **Ton statut** : `RADAR_STATUS` dans `secrets.py`, partagé avec les autres badges Radar (nom + statut : 25 octets au total).
- **Select** passe de la vue radar à la liste, **↑ / ↓** fait défiler la liste. Les LED du boîtier brillent plus fort quand un badge s'approche.
- Seuls les badges sont affichés, jamais les téléphones ou autres appareils Bluetooth.

## Captures d'écran

```powershell
./tools/screenshot.ps1                      # refait toutes les captures de docs/screenshots/
./tools/screenshot.ps1 -App snake -Seconds 5 # une seule app
```

Le script lance l'app par la console série, la laisse tourner quelques secondes, récupère l'image de l'écran (RGB565, 320×240 ou 160×120) et l'enregistre en PNG agrandi ×2. La liste des captures et leur réglage (`setup`, par exemple ouvrir une page ou simuler des badges) est dans `docs/screenshots/captures.json`. Il faut compter environ 25 s par capture.

Après une modification d'app : `./tools/deploy.ps1`, puis `./tools/screenshot.ps1`.

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
