# badger

Mes modifications du badge **GitHub Universe '26** (Badger 2350 : RP2350, écran 320×240, MonaOS 4.0, MicroPython).

## Contenu

| Dossier | Rôle |
|---|---|
| `system/` | Copie exacte du lecteur USB du badge (`/system` sur l'appareil) : `main.py`, l'animation de démarrage, les apps et les assets |
| `tools/` | Scripts à lancer sur le PC (génération des QR codes, etc.) |
| `secrets.example.py` | Modèle des réglages ; le vrai `secrets.py` n'est jamais commité |

## Installer sur le badge

1. Mettre le badge en mode clé USB (app **Mass Storage**, ou deux appuis rapides sur RESET).
2. Copier le contenu de `system/` sur le lecteur **BADGER**.
3. Éjecter le lecteur, puis redémarrer le badge.

Pour les réglages, copier `secrets.example.py` en `secrets.py` sur le lecteur et le remplir, ou utiliser l'app **Settings** du badge.

## Bon à savoir

- `/system` est en lecture seule pour le badge : on le modifie uniquement par le lecteur USB.
- Les caches et sauvegardes (stats GitHub, succès, contacts…) vivent dans `/state`, hors du lecteur USB.
- Console MicroPython sur le port série du badge (115200 bauds), par exemple avec Thonny.
