"""Checks every app in system/apps, so a new app shows up well in the menu and
in Badge Studio: an __init__.py, a README.md and a 24x24 icon.png for the
apps added to the badge, no path into another app's folder, and the
template of tools/new_app.py still compiling.

Run from the repo root: py tests/test_apps.py
"""
import os
import re
import struct
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS = os.path.join(ROOT, "system", "apps")
TEMPLATE = os.path.join(ROOT, "templates", "app")

# The apps that came with the badge: they keep MonaOS's built-in icons
STOCK = {
    "badge", "brattal", "contacts", "flappy_mona", "iss", "life", "mass_storage", "menu",
    "merge_conflict", "mona_paint", "mona_pet", "pong", "rogue", "settings", "show", "snake",
}
SLUG = re.compile(r"^[a-z][a-z0-9_]*$")


def apps():
    for slug in sorted(os.listdir(APPS)):
        folder = os.path.join(APPS, slug)
        if os.path.isdir(folder) and not slug.startswith((".", "_")):
            yield slug, folder


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG file"
    return struct.unpack(">II", head[16:24])


class AppsTest(unittest.TestCase):
    def test_every_app_starts(self):
        for slug, folder in apps():
            with self.subTest(app=slug):
                self.assertRegex(slug, SLUG, "folder names are lowercase, digits and _")
                self.assertTrue(
                    os.path.exists(os.path.join(folder, "__init__.py"))
                    or os.path.exists(os.path.join(folder, "__init__.mpy")),
                    "an app needs an __init__.py",
                )

    def test_new_apps_have_readme_and_icon(self):
        for slug, folder in apps():
            if slug in STOCK:
                continue
            with self.subTest(app=slug):
                self.assertTrue(os.path.exists(os.path.join(folder, "README.md")), "add a README.md: Badge Studio shows it")
                icon = os.path.join(folder, "icon.png")
                self.assertTrue(os.path.exists(icon), "add a 24x24 icon.png for the menu")

    def test_icons_are_24x24(self):
        for slug, folder in apps():
            icon = os.path.join(folder, "icon.png")
            if os.path.exists(icon):
                with self.subTest(app=slug):
                    self.assertEqual(png_size(icon), (24, 24))

    def test_apps_only_use_their_own_folder(self):
        # Badge Studio installs an app in /apps/<slug> and rewrites
        # /system/apps/<slug>: a path into another app would break there
        others = re.compile(r"/system/apps/([a-z0-9_]+)")
        for slug, folder in apps():
            if slug in STOCK:
                continue
            for name in os.listdir(folder):
                if not name.endswith(".py"):
                    continue
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    found = set(others.findall(f.read())) - {slug}
                with self.subTest(app=slug, file=name):
                    self.assertFalse(found, f"paths into other apps: {sorted(found)}")

    def test_template_compiles(self):
        for name in os.listdir(TEMPLATE):
            if name.endswith(".py"):
                with open(os.path.join(TEMPLATE, name), encoding="utf-8") as f:
                    compile(f.read(), name, "exec")


if __name__ == "__main__":
    unittest.main(verbosity=1)
