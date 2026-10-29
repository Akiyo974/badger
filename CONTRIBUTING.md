# Contributing

Thanks for wanting to help! This repo is a playground for the **GitHub Universe '26 badge** (Badger 2350, MicroPython, MonaOS 4.0), and every app added here shows up in [Badge Studio](https://akiyo974.github.io/badger/studio/)'s store for every badge owner.

You don't need a badge for everything: the site, Badge Studio, the docs and the tests run on any computer.

## Ways to help

| You have… | You can |
|---|---|
| 5 minutes | Report a bug, suggest an app idea, fix a typo ([open an issue](https://github.com/Akiyo974/badger/issues/new/choose)) |
| An evening and a badge | **Make an app** (below) or improve one: Radar, Duck Maze, Pedometer… |
| An evening, no badge | Improve [Badge Studio](docs/studio/) or the [home page](docs/index.html), write tests, improve the docs |
| Questions | Ask in [Discussions](https://github.com/Akiyo974/badger/discussions) |

Issues labelled [`good first issue`](https://github.com/Akiyo974/badger/labels/good%20first%20issue) are small and well described: a good place to start.

## Make your first app in 10 minutes

### 1. Get the code

Fork the repo on GitHub, then:

```bash
git clone https://github.com/<you>/badger.git
cd badger
git checkout -b feat/my-app
```

You need Python 3 with [Pillow](https://pypi.org/project/pillow/) (`pip install pillow`) for the tools that draw images.

### 2. Create the app

```bash
py tools/new_app.py my_app "My App" "One line about what it does."
```

This creates `system/apps/my_app/` from [`templates/app`](templates/app):

| File | What it is |
|---|---|
| `__init__.py` | The app. MonaOS runs it when you open it from the menu; `run(update)` calls `update()` every frame |
| `README.md` | What it does and its controls. Badge Studio shows it in the store |
| `icon.png` | The 24×24 menu icon. Redraw it: pixel art in Python (see `tools/make_maze_art.py`) or any pixel editor |

The template draws a square you move with the arrows: change it into your idea.

### 3. Try it on the badge

Plug the badge in over USB and switch it on.

- **Windows**: `./tools/deploy.ps1 -Only apps/my_app` copies the app and reboots the badge. Your app is in the menu.
- **Any computer**: push your branch, open [Badge Studio](https://akiyo974.github.io/badger/studio/) in Chrome or Edge, connect the badge, pick **Another repository…** in the store and type `<you>/badger@feat/my-app`. Install your app from there.
- **By hand**: switch the badge to USB drive mode (Mass Storage app), copy your folder into the drive's `apps` folder, eject, restart.

Errors are printed on the serial console: Badge Studio's **Console** tab shows them.

To add a screenshot to the README gallery: `./tools/screenshot.ps1 -App my_app` (or the **Screenshot** tab of Badge Studio).

### 4. Open a pull request

```bash
py tests/test_apps.py
git add system/apps/my_app
git commit -m "My App: one line about what it does"
git push -u origin feat/my-app
```

Then open the pull request on GitHub. The template asks a few questions; a screenshot or a short video of the app on the badge helps a lot.

## Rules of thumb for apps

- **Stay in your folder.** Refer to your files with relative paths or `/system/apps/<your_app>/…`: Badge Studio rewrites that path when it installs an app in `/apps`. Never write into another app's folder.
- **Save state in `/state`**, the writable part of the badge (`State.save` / `State.load` from `badgeware`, or a JSON file `/state/<your_app>.json`).
- **Settings go in `secrets.py`** (read with `getattr(secrets, "MY_SETTING", default)`), and are documented in `secrets.example.py`. Never commit a real `secrets.py`.
- **Keep it fast.** 30 frames per second is the goal: draw what changes, keep big images in memory once. Memory is tight: free what you no longer need.
- **Look like the badge.** The contribution greens (`#0e4429`, `#006d32`, `#26a641`, `#39d353`), dark backgrounds and Mona's palette fit in best.
- **Works without extras.** Wi-Fi, the watch and Qw/ST add-ons are optional: the app should still open without them.

## Code style

- Python reads like the existing apps: plain names, short functions, comments that say *why*.
- Repo content (code, comments, docs, commits) is in **English**.
- Every pull request adds a line to [`CHANGELOG.md`](CHANGELOG.md) under **Unreleased**.
- CI runs on every pull request: syntax of `system/`, the tests in `tests/`, the Badge Studio scripts and the Wear OS watch app.

## Working on Badge Studio and the site

They are static files in [`docs/`](docs): no build step.

```bash
py -m http.server 8765 --directory docs
```

Then open <http://localhost:8765/> (home page) and <http://localhost:8765/studio/> (Badge Studio, in Chrome or Edge for Web Serial). Check the scripts with `node --check docs/studio/studio.js docs/site.js`.

## Be kind

Everyone here is welcome, whatever their level. Please read the [Code of Conduct](CODE_OF_CONDUCT.md).

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
