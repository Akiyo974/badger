"""Checks docs/catalog.json, the fallback app list of the site and Badge
Studio: it must hold every built-in source of docs/site.js and
docs/studio/studio.js (the store and Repair), under the key they look up.
Repair's factory reference must be the repo's first commit.

Run from the repo root: py tests/test_catalog.py
"""
import json
import os
import re
import subprocess
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


    def test_factory_reference_is_the_first_commit(self):
        # Repair's "as shipped" reference is the commit that holds the badge's drive untouched
        with open(os.path.join(ROOT, "docs", "studio", "studio.js"), encoding="utf-8") as file:
            factory = re.search(r'id: "repair-factory".*?branch: "([0-9a-f]{40})"', file.read()).group(1)
        try:
            roots = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=ROOT,
                                   capture_output=True, text=True, check=True).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("no git history")
        if subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT,
                          capture_output=True, text=True, check=False).stdout.strip() == "true":
            self.skipTest("shallow clone")
        self.assertIn(factory, roots)


if __name__ == "__main__":
    unittest.main()
