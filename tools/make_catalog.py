"""Writes docs/catalog.json: the app files of the store's sources, as the GitHub
API lists them.

The site and Badge Studio read the store from the GitHub API, which allows a
visitor 60 requests an hour per IP address: on a busy conference Wi-Fi, many
visitors share one. When the API refuses, they fall back to this file, kept
up to date by .github/workflows/catalog.yml.

The file list comes from git (ls-tree gives the same blob sha and size as the
API), so making it needs no token and has no rate limit.

Usage, from the repo root: py tools/make_catalog.py
"""
import json
import subprocess
import tempfile

# Same sources as SOURCES in docs/site.js and REPAIR_SOURCES in
# docs/studio/studio.js. A branch, or a commit for a fixed reference
SOURCES = (
    ("badger/home", "main", "badge/apps"),
    ("Akiyo974/badger", "main", "system/apps"),
    # Repair: the whole drive, as shipped (first commit) and with this repo's changes
    ("Akiyo974/badger", "6912f14355e5603f5793e61baf7acbe1889146c0", "system"),
    ("Akiyo974/badger", "main", "system"),
)
OUTPUT = "docs/catalog.json"


def tree(repo, ref, base):
    with tempfile.TemporaryDirectory() as folder:
        # Only the one commit, no checkout: the file list is all that is needed.
        # fetch (not clone --branch) also takes a commit id
        for command in (
            ["init", "--quiet"],
            ["fetch", "--quiet", "--depth", "1", f"https://github.com/{repo}.git", ref],
        ):
            subprocess.run(["git", "-C", folder, *command], check=True)
        listing = subprocess.run(
            ["git", "-C", folder, "ls-tree", "-r", "-l", "FETCH_HEAD", "--", base],
            check=True, capture_output=True, text=True,
        ).stdout
    entries = []
    for line in listing.splitlines():
        meta, path = line.split("\t", 1)
        _mode, kind, sha, size = meta.split()
        if kind == "blob":
            entries.append({"path": path, "sha": sha, "size": int(size)})
    return entries


def main():
    trees = {f"{repo}@{branch}:{base}": tree(repo, branch, base) for repo, branch, base in SOURCES}
    text = json.dumps({"trees": trees}, indent=1, sort_keys=True) + "\n"
    try:
        with open(OUTPUT, encoding="utf-8") as file:
            if file.read() == text:
                print(OUTPUT, "is up to date")
                return
    except FileNotFoundError:
        pass
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as file:
        file.write(text)
    print("Wrote", OUTPUT, {key: len(entries) for key, entries in trees.items()})


if __name__ == "__main__":
    main()
