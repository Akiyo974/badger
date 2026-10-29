"""Checks docs/guides: every guide is listed in its README and on the site
(GUIDES in guides.js), and its links to other guides and screenshots exist.

Run from the repo root: py tests/test_guides.py
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUIDES = os.path.join(ROOT, "docs", "guides")
LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")


def guides():
    return sorted(name[:-3] for name in os.listdir(GUIDES) if name.endswith(".md") and name != "README.md")


class GuidesTest(unittest.TestCase):
    def test_every_guide_is_listed(self):
        with open(os.path.join(GUIDES, "README.md"), encoding="utf-8") as file:
            readme = file.read()
        with open(os.path.join(GUIDES, "guides.js"), encoding="utf-8") as file:
            script = file.read()
        for name in guides():
            self.assertIn(f"({name}.md)", readme, f"{name}.md is not in docs/guides/README.md")
            self.assertIn(f'["{name}", ', script, f"{name} is not in GUIDES of docs/guides/guides.js")

    def test_local_links_exist(self):
        for name in [*guides(), "README"]:
            with open(os.path.join(GUIDES, name + ".md"), encoding="utf-8") as file:
                text = file.read()
            for target in LINK.findall(text):
                if re.match(r"^[a-z]+:", target):
                    continue
                self.assertTrue(os.path.exists(os.path.normpath(os.path.join(GUIDES, target))), f"{name}.md links to {target}")


if __name__ == "__main__":
    unittest.main()
