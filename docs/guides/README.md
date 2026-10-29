# Guides

Step-by-step guides for the apps made or changed in this repo. Read them here on GitHub, or on the site: **[akiyo974.github.io/badger/guides](https://akiyo974.github.io/badger/guides/)**.

| Guide | In one line |
|---|---|
| [Badge](badge.md) | Your GitHub profile, QR codes, an NFC contact card and an LED matrix graph |
| [Contacts](contacts.md) | Swap contact cards by holding two badges back to back |
| [Radar](radar.md) | See the badges around you, and play Hot / Cold to find someone |
| [Duck Maze](duck_maze.md) | Tilt the badge to roll a marble through six mazes |
| [Pedometer](pedometer.md) | The day's steps from your watch, hour by hour |
| [Mona Pet](mona_pet.md) | Look after Mona; your steps feed her |
| [Menu](menu.md) | The home screen: CUSTOM band, installed apps, and a dizzy Mona |
| [Badger Remote](badger_remote.md) | Use a Wear OS watch as the badge's buttons |

## Before you start: installing the apps

Everything is done from **[Badge Studio](https://akiyo974.github.io/badger/studio/)**, in Chrome or Edge on a computer, with the badge plugged in over USB.

1. Press **Connect badge**.
2. Open the **Extensions** tab and press **Compare with the badge**. It lists the apps of this repo that are missing or different on your badge.
3. Press **Switch to USB drive mode**, then **Pick the apps folder** and choose the `apps` folder of the **BADGER** drive.
4. Press **Add to the badge** (new apps) or **Install this version** (Badge, Contacts, Mona Pet, Menu). The current version is backed up first and can be restored from *Backups on the drive*.
5. Press **Restart the badge**.

Install the **Menu** first: it shows the CUSTOM band and the apps installed from the store.

On Windows, `./tools/deploy.ps1` from a clone of the repo does the same in one go (see the [README](https://github.com/Akiyo974/badger#deploying-to-the-badge)).

## Your settings

Most apps read your details from `secrets.py` on the badge. Set them in the **Settings** tab of Badge Studio, or edit `secrets.py` on the BADGER drive, next to `main.py` (at the root of the drive, or in its `system` folder on some firmware); start from [`secrets.example.py`](https://github.com/Akiyo974/badger/blob/main/secrets.example.py):

| Setting | Used by |
|---|---|
| `WIFI_SSID`, `WIFI_PASSWORD` | Badge (2.4 GHz networks only) |
| `GITHUB_USERNAME` | Badge, Contacts |
| `CONTACT_NAME`, `CONTACT_LINKEDIN`, `CONTACT_WEBSITE` | Badge (NFC card), Contacts, Radar |
| `CONTACT_TITLE`, `CONTACT_COMPANY`, `NFC_CARD` | Badge (NFC card) |
| `RADAR_STATUS` | Radar |
| `WATCH_REMOTE` | Badger Remote |
| `STEPS_GOAL` | Pedometer |

## Something broken?

The **Repair** tab of Badge Studio puts back missing or damaged files: see [Repairing the badge](https://github.com/Akiyo974/badger#repairing-the-badge). Errors from an app are printed in the **Console** tab.
