"""Creates a new badge app from templates/app, ready to edit and deploy.

Writes system/apps/<slug>/ with:
- __init__.py: a small working app (a square moved with the arrows);
- README.md: what the app does, shown in Badge Studio's store;
- icon.png: a 24x24 menu icon to redraw.

Usage, from the repo root:
  py tools/new_app.py my_app "My App" "One line about what it does."
Then: ./tools/deploy.ps1 -Only apps/my_app
"""
import os
import re
import shutil
import sys

from PIL import Image

TEMPLATE = "templates/app"
APPS = "system/apps"
# A 3x3 contribution graph: each square is 6 px, 1 px apart, centred
ICON_LEVELS = ("gGH", "GHL", "HLL")
COLOURS = {".": (13, 17, 23), "g": (14, 68, 41), "G": (0, 109, 50), "H": (38, 166, 65), "L": (57, 211, 83)}


def main(slug, title, summary):
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", slug):
        raise SystemExit("The app name is a folder name: lowercase letters, digits and _, like my_app.")
    target = f"{APPS}/{slug}"
    if os.path.exists(target):
        raise SystemExit(f"{target} already exists.")
    shutil.copytree(TEMPLATE, target)
    for name in ("__init__.py", "README.md"):
        path = f"{target}/{name}"
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = text.replace("APP_TITLE", title).replace("APP_SUMMARY", summary)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    icon = Image.new("RGB", (24, 24), COLOURS["."])
    for row, levels in enumerate(ICON_LEVELS):
        for column, cell in enumerate(levels):
            left, top = 2 + column * 7, 2 + row * 7
            icon.paste(COLOURS[cell], (left, top, left + 6, top + 6))
    icon.save(f"{target}/icon.png")
    print(f"Created {target}. Try it: ./tools/deploy.ps1 -Only apps/{slug}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
