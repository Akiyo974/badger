# badger

My mods for the **GitHub Universe '26** badge (Badger 2350: RP2350, 320×240 colour screen, MonaOS 4.0, MicroPython).

<p align="center">
  <img src="docs/screenshots/menu.png" width="320" alt="MonaOS menu">
  <img src="docs/screenshots/badge.png" width="320" alt="Badge app: GitHub stats">
</p>

## Gallery

Screenshots taken straight from the badge with `tools/screenshot.ps1`.

### Apps changed in this repo

| Badge | Badge: QR codes | Contacts |
|---|---|---|
| ![Badge](docs/screenshots/badge.png) | ![Website QR code](docs/screenshots/badge-qr.png) | ![Contacts](docs/screenshots/contacts.png) |
| **Radar** | **Radar: list** | |
| ![Radar](docs/screenshots/radar.png) | ![Radar list](docs/screenshots/radar-list.png) | |

The badges on the Radar screenshots are simulated (I only have one badge).

### Stock apps

| Menu | Snake | Pong |
|---|---|---|
| ![Menu](docs/screenshots/menu.png) | ![Snake](docs/screenshots/snake.png) | ![Pong](docs/screenshots/pong.png) |
| **Merge Conflict** | **Flappy Mona** | **Mona Pet** |
| ![Merge Conflict](docs/screenshots/merge_conflict.png) | ![Flappy Mona](docs/screenshots/flappy_mona.png) | ![Mona Pet](docs/screenshots/mona_pet.png) |
| **Mona Paint** | **Rogue** | **Brattal** |
| ![Mona Paint](docs/screenshots/mona_paint.png) | ![Rogue](docs/screenshots/rogue.png) | ![Brattal](docs/screenshots/brattal.png) |
| **Life** | **ISS** | |
| ![Life](docs/screenshots/life.png) | ![ISS](docs/screenshots/iss.png) | |

## What's inside

| Folder | Purpose |
|---|---|
| `system/` | Exact copy of the badge's USB drive (`/system` on the device): `main.py`, the boot animation, apps and assets |
| `tools/` | PC scripts: deploy, screenshots, contacts export, QR codes |
| `docs/screenshots/` | README screenshots and their list (`captures.json`) |
| `secrets.example.py` | Settings template; the real `secrets.py` is never committed |
| `CHANGELOG.md` | Change history |

The stock badge software in `system/` (MonaOS and its apps) belongs to its authors and is included here so the changes can be read and deployed. Fonts are under the SIL Open Font License (`system/assets/fonts/licences/OFL.txt`).

## Deploying to the badge

Plug the badge in over USB, then from the repo root:

```powershell
./tools/deploy.ps1
```

The script:
1. finds the badge (serial port and **BADGER** drive) and switches it to USB drive mode if needed;
2. copies only the files whose **content** changed (dates don't count, git changes them on every checkout);
3. never touches `secrets.py` and never deletes anything on the badge;
4. reboots the badge into normal mode.

| Option | Effect |
|---|---|
| `-DryRun` | Lists the files that would be copied, without writing anything |
| `-Only apps/badge` | Deploys only one folder of `system/` |
| `-NoReboot` | Leaves the badge in USB drive mode after copying |
| `-Port COM4` | Forces the serial port if detection fails |

To try a pull request: `git checkout <branch>` then `./tools/deploy.ps1`.

### By hand

1. Put the badge in USB drive mode (**Mass Storage** app, or double-tap RESET).
2. Copy the contents of `system/` to the **BADGER** drive.
3. Eject the drive, then restart the badge.

## Apps added or changed

| App | What changes |
|---|---|
| **Badge** | QR code pages (↑ / ↓) and a "Last push" line under the name |
| **Contacts** | Received links are checked, website field, delete a contact, export to the PC |
| **Radar** (new) | The badges around you, placed by distance, with their name and status |

### Radar

- **Distance only**: Bluetooth gives a signal strength, not a direction. The closer a badge is to the centre, the nearer it is; its angle is just a fixed spot derived from its id.
- **Visible badges**: every badge running Radar, and stock badges while they are in Contacts, Pong or Merge Conflict (their Bluetooth only advertises then).
- **Your status**: `RADAR_STATUS` in `secrets.py`, shared with other Radar badges (name + status: 25 bytes in total).
- **Select** switches between the radar and the list, **↑ / ↓** scrolls the list. The case lights glow brighter as a badge gets closer.
- Only badges are shown, never phones or other Bluetooth devices.

## Screenshots

```powershell
./tools/screenshot.ps1                       # retakes every screenshot in docs/screenshots/
./tools/screenshot.ps1 -App snake -Seconds 5 # a single app
```

The script starts the app over the serial console, lets it run for a few seconds, reads the screen buffer (RGB565, 320×240 or 160×120) and saves it as a PNG scaled ×2. The list of screenshots and their settings (`setup`, e.g. to open a page or simulate badges) lives in `docs/screenshots/captures.json`. Allow about 25 s per screenshot.

After changing an app: `./tools/deploy.ps1`, then `./tools/screenshot.ps1`.

## Exporting contacts

```powershell
./tools/export_contacts.ps1 -OutDir ~/Desktop
```

Reads the cards swapped with the **Contacts** app (in `/state`, outside the USB drive) and writes `contacts.csv` and `contacts.vcf`, ready to import into a phone, Outlook or Google Contacts.

## Tests

```powershell
py tests/test_contacts_compat.py
```

Simulates card swaps between the stock Contacts app (read from the first commit) and the version in this repo, to check that swapping with an unmodified badge still works.

## Settings

Use the badge's **Settings** app, or copy `secrets.example.py` to `secrets.py` on the drive and fill it in.

## How I work

- `main` is always deployable.
- Every change goes through a branch (`feat/…`, `fix/…`) and a pull request, tested on the badge with `deploy.ps1` and reviewed by Copilot before merging.
- Every PR adds its line to `CHANGELOG.md`, under "Unreleased".

## Good to know

- `/system` is read-only for the badge itself: it is only changed through the USB drive.
- Caches and saves (GitHub stats, achievements, contacts…) live in `/state`, outside the USB drive.
- MicroPython console on the badge's serial port (115200 baud), e.g. with Thonny.
