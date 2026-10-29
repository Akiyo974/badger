# Changelog

Notable changes to this repo. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added
- Store fallback: when the GitHub API rate limit is reached (shared Wi-Fi), the home page and Badge Studio read `docs/catalog.json`, the same app list made by `tools/make_catalog.py` from git and refreshed hourly by `.github/workflows/catalog.yml`; `tests/test_catalog.py` checks every built-in source is in it.
- Home page and Badge Studio: on a phone or tablet, a note says Badge Studio needs a computer, with a button to share or copy the link. The home page search also matches app descriptions.
- Links to the official [badge simulator](https://badger.github.io/editor) for trying an app without a badge, and to the official site's store in the README.
- `CREDITS.md` (authors, licenses, trademarks), `SECURITY.md` (private reporting, keeping `secrets.py` out of git) and `PRIVACY.md` (no tracking; what each app shares nearby), linked from the README, the contributing guide, the issue chooser and the site footer.
- **Contributing**: `CONTRIBUTING.md` with a 10-minute first app, `CODE_OF_CONDUCT.md`, MIT `LICENSE`, issue forms (bug, app idea), a pull request template, and a contributing section on the home page and in the README.
- `tools/new_app.py` creates an app from `templates/app` (a working app, README and icon); `tests/test_apps.py` (in CI) checks every app has what the menu and Badge Studio need.
- Badge Studio: **Another repository…** adds any GitHub repository, branch or folder as a store source, to try an app from a fork before its pull request.
- `tools/screenshot.ps1 -App /apps/<name>` captures apps installed outside `/system`.
- Home page: the whole app store (official apps and this repo's), read live from GitHub, with screenshots, search and filters; each app opens its page in Badge Studio (`studio/#app=<source>/<slug>`). Share image `docs/media/og.png` and a 20-second video `docs/media/badge-studio.mp4`, both drawn by `tools/make_promo.py`.
- READMEs for Duck Maze, Pedometer, Contacts and Mona Pet, shown in the store.

### Fixed
- Badge Studio, from the review of #20: an update is written apart and only replaces the installed app once complete; one install, uninstall or restore at a time; backups without their manifest cannot be restored; the serial link frees its locks on errors, times out cleanly and only buffers output a command waits for; the hero hides once connected; the Screenshot list fills on the first connection; a late catalogue no longer overwrites another; settings have accessible names; apps can change section from the keyboard.
- **Badge Studio** (`docs/studio/`, on GitHub Pages): manage the badge from Chrome or Edge over Web Serial. App store (official apps and this repo) installing to `/apps` with checked writes, home screen editor (order, CUSTOM band, hidden apps), extensions that replace built-in apps through USB drive mode with backups and restore, settings, screenshots and a console.
- Menu: apps in `/apps` (installed from Badge Studio) show up under an **INSTALLED** band; `/state/menu_layout.json` can set the order, the CUSTOM apps and the hidden ones.
- GitHub Pages landing page (`docs/index.html`).
- Menu: **shake the badge** and Mona gets dizzy, with X eyes and rubber ducks circling her head; any button closes it. Sprites drawn by `tools/make_dizzy_sprites.py` in Mona's palette.
- **Duck Maze** app: tilt the badge to roll a marble through 6 levels drawn like a contribution graph, collecting rubber ducks and avoiding bug holes; best times and unlocked levels saved; listed under CUSTOM in the menu. Level checks in `tests/test_duck_maze.py` (run in CI) and art drawn by `tools/make_maze_art.py`.
- Menu: the apps this repo changed or added (Badge, Contacts, Radar, Mona Pet, Pedometer) come first under a **CUSTOM** band, the stock ones follow under **STOCK** (`CUSTOM_APPS` in `menu/app.py`).
- **Steps from the watch**: Badger Remote reads the day's steps from Health Services (total and per hour, recorded in the background) and sends them to the badge on a second characteristic; `remote.py` keeps the last ones in `/state/watch_steps`. The badge can count steps with its own LSM6DS3 too, but it is not used: worn around the neck, it does not count reliably.
- **Pedometer** app: the day's steps from the watch, GitHub Universe day, hourly squares, distance, goal (`STEPS_GOAL`) and sync time.
- Mona Pet: steps from the watch feed Mona (500 steps = 1 meal) and lift her mood; Down now shows her walk instead of the stats.
- `tests/test_watch_steps.py`: the steps format shared with the watch, the Pedometer and Mona's meals.
- Radar: opt-in **Hot / Cold** game for a selected badge, with a signal gauge, warmer/colder feedback, target-only lights and haptics, and manual **Found!** confirmation.
- Radar: persistent history of the 200 most recent distinct badges in `/state/radar_history.json`, with names, status and visit counts; open it with Right from the radar.
- Radar behavior tests in CI, covering BLE traffic, stock compatibility, proximity, fading, history and game controls.
- Badge app: the NFC tag holds a **contact card** (vCard with name, title, company and labelled Website / LinkedIn / GitHub links), followed by the website link; `CONTACT_TITLE`, `CONTACT_COMPANY` and `NFC_CARD` in `secrets.py`.
- Badge app: **reaction when a phone scans the tag**, detected through the ST25DV's RF field status: Mona with hearts and "thanks for the scan!" on screen, a pulsing heart on the LED matrix, a buzz from the DRV2605 and a scan counter.
- Hardware add-ons on the Qw/ST port, all optional: a 13×9 RGB LED matrix (IS31FL3741) shows the contribution graph in Badge and a mini radar in Radar; an NFC tag (ST25DV) is programmed with the website link by Badge; a haptic driver (DRV2605) makes Radar vibrate when a badge shows up.
- Menu: apps without a built-in icon can ship an `icon.png`, which Radar now does. Badge and Radar also have their own `README.md`.
- **Badger Remote** (`wear/`): Wear OS watch app that presses the badge's buttons over Bluetooth LE (tap, hold, crown for ↑ / ↓), with `system/remote.py` on the badge side (`WATCH_REMOTE` in `secrets.py`).
- GitHub Actions: CI (syntax of `system/`, contacts test, watch app build, tests and lint) and signed watch app releases on `wear-v*` tags.
- `tools/screenshot.ps1`: screenshots of the apps taken on the badge over the serial console (PNG ×2), listed in `docs/screenshots/captures.json`.
- README: gallery of 16 screenshots (changed apps and stock apps).
- **Radar** app: nearby badges placed by distance (Bluetooth signal strength), with name, identicon, current app and status. List view with Select, case lights driven by proximity, personal status `RADAR_STATUS`.
- Contacts app: "website" field on the card (`CONTACT_WEBSITE`), shown as a QR code. Stock badges ignore it, so swapping with them still works.
- Contacts app: delete a contact (↓ on its card, then confirm).
- `tools/export_contacts.ps1`: exports the badge's contacts to `contacts.csv` and `contacts.vcf`.
- `tests/test_contacts_compat.py`: simulates swaps between the stock app and the modified one.
- Badge app: QR code pages (website, LinkedIn, GitHub) with ↑ / ↓ from the stats view, images generated by `tools/make_qr.py`.
- Badge app: "Last push" line under the name (e.g. `Last push: highlight - 1d ago`), refreshed on every launch and cached for offline use.
- `tools/deploy.ps1`: deploys `system/` to the badge in one command. It switches the badge to USB drive mode, copies only the files whose content changed, never touches `secrets.py`, then reboots the badge. Options `-DryRun`, `-Only`, `-NoReboot` and `-Port`.
- `CHANGELOG.md`.

### Changed
- README: Mona Pet and the Menu move to the "Apps changed in this repo" gallery; new menu screenshot.
- README: new "Built-in sensors" section (motion sensor and its events, orientation, light, buttons, battery), with values measured on the badge.
- README: `tests/` listed in the repo contents; hardware table updated for the Radar changes (fading and Hot / Cold on the matrix, merged arrival vibrations and Hot / Cold pulses); Radar README mentions the DRV2605L.
- Radar: **Very near / Near / Far** replace metre estimates; labelled rings explicitly represent signal strength, not direction. Badges fade from 4 to 12 seconds without a signal, including matrix and case-light feedback.
- Radar detection: filter unrelated packets before queuing, coalesce repeat announcements, prioritise identities under load, preserve address types, and smooth RSSI with a median, time-based filter and hysteresis.
- The repo is now in English (README, changelog, tools and tests).
- README: deploying, settings and pull-request workflow sections.
- `.gitignore`: ignores the local `.local/` folder (drafts and backups).

### Fixed
- Radar: nearby icons no longer cover the centre marker; game selection follows badge identity when proximity rankings change. Arrival vibrations no longer build an unbounded backlog.
- `deploy.ps1` failed on files at the root of `system/` (`main.py`…): it tried to create the drive root as a folder.
- `deploy.ps1 -DryRun` reboots the badge back to normal mode when it had to switch it to USB drive mode.
- `export_contacts.ps1` only targets the Universe '26 badge and asks for `-Port` when several are plugged in, like the other tools.
- Contacts app: the third link line (website) overflowed the card; the card is taller and the illustration below it moved down.
- Badge app: the "Last push" line no longer shows another account's activity after `GITHUB_USERNAME` changes, and clears when GitHub returns no events.
- `deploy.ps1`: stops without rebooting the badge if Windows cannot finish writing, instead of waiting 2 s and risking corrupted files.
- `deploy.ps1`: only targets the badge (`VID_2E8A&PID_1101`), ties the serial port to its drive through the USB serial number, and asks for `-Port` when several badges are plugged in. Deployment stops if the chosen port cannot be tied to its drive.
- `deploy.ps1`: a `-Port` given by hand is no longer replaced after switching to USB drive mode.
- `deploy.ps1`: `-Only` is normalised (`.`, `..`, slashes) and must stay inside `system/`; before, `-Only .` copied `main.py` as `ain.py`.

### Security
- Contacts app: received links are checked before being saved: LinkedIn only on `linkedin.com`, valid GitHub username, website over `https://`. Dubious links are dropped, but the swap still completes on both sides.
- Contacts app: address book capped at 200 contacts.

## 2026-10-27: stock version

- Copy of the GitHub Universe '26 badge as shipped (MonaOS 4.0, MicroPython 1.29) in `system/`.
- `secrets.example.py`, `tools/make_qr.py` and LF line endings.
