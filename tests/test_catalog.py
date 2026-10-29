"""Checks docs/catalog.json, the fallback app list of the site and Badge
Studio: it must hold every built-in source of docs/site.js and
docs/studio/studio.js, under the key they look up, with apps in it.

Run from the repo root: py tests/test_catalog.py
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = re.compile(r'repo: "([^"]+)", branch: "([^"]+)", base: "([^"]+)"')


class CatalogTest(unittest.TestCase):
    def test_every_source_is_in_the_catalog(self):
        with open(os.path.join(ROOT, "docs", "catalog.json"), encoding="utf-8") as file:
            trees = json.load(file)["trees"]
        for script in ("docs/site.js", "docs/studio/studio.js"):
            with open(os.path.join(ROOT, script), encoding="utf-8") as file:
                sources = SOURCE.findall(file.read())
            self.assertTrue(sources, script)
            for repo, branch, base in sources:
                key = f"{repo}@{branch}:{base}"
                self.assertIn(key, trees, f"{script}: run py tools/make_catalog.py")
                self.assertTrue(any(e["path"].endswith("/__init__.py") for e in trees[key]), key)


if __name__ == "__main__":
    unittest.main()
