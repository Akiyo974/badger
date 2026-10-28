"""Simulates card swaps between the stock Contacts app and the modified one.

Run from the repo root: py tests/test_contacts_compat.py
"""
import os
import subprocess
import sys
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCK_COMMIT = "6912f14"  # stock badge version
SOURCES = {"new": f"{ROOT}/system/apps/contacts/__init__.py"}

for name in ("hints", "missing_details", "pairing", "badgeware", "secrets"):
    sys.modules[name] = MagicMock()


def load(kind, secrets):
    sys.modules["secrets"] = MagicMock(**secrets)
    ns = {"__name__": kind, "run": lambda f: None, "reset": lambda: None}
    for name in ("badge", "screen", "image", "color", "font", "rect", "HIRES", "VSYNC",
                 "BUTTON_LEFT", "BUTTON_RIGHT", "BUTTON_SELECT", "BUTTON_UP", "BUTTON_DOWN", "BUTTON_BACK"):
        ns[name] = MagicMock()
    if kind == "stock":
        source = subprocess.run(["git", "show", f"{STOCK_COMMIT}:system/apps/contacts/__init__.py"], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")
    else:
        source = open(SOURCES[kind], encoding="utf-8").read()
    exec(source, ns)
    return ns


class FakeLink:
    def __init__(self, mtu_payload):
        self.inbox = []
        self.peer = None
        self.mtu_payload = mtu_payload

    def capacity(self):
        return self.mtu_payload

    def send(self, message):
        self.peer.inbox.append(bytes(message))
        return True


def swap(kind_a, card_a, kind_b, card_b, mtu=20):
    a, b = load(kind_a, {}), load(kind_b, {})
    la, lb = FakeLink(mtu), FakeLink(mtu)
    la.peer, lb.peer = lb, la
    sa, sb = a["Swap"](card_a, b"B" * 8), b["Swap"](card_b, b"A" * 8)
    for _ in range(50):
        sa.pump(la)
        sb.pump(lb)
        for link, s in ((la, sa), (lb, sb)):
            while link.inbox:
                s.receive(link.inbox.pop(0), link)
        if sa.done and sb.done:
            break
    saved_a = a.get("safe_card", lambda c: c)(sa.card) if sa.card else None
    saved_b = b.get("safe_card", lambda c: c)(sb.card) if sb.card else None
    return sa.done, sb.done, saved_a, saved_b


new_ns = load("new", {})
mine = {"name": "Christen Dijoux", "github": "Akiyo974",
        "linkedin": "https://www.linkedin.com/in/christen-dijoux", "website": "https://christendijoux.com/"}
other = {"name": "Ada Lovelace", "github": "ada", "linkedin": ""}
phish = {"name": "Free Swag", "github": "bad name!", "linkedin": "https://evil.example/in/x"}
mixed = {"name": "Bob", "github": "bob-dev", "linkedin": "https://evil.example/in/bob"}

results = []
def check(label, got, expected):
    ok = got == expected
    results.append(ok)
    print(("OK  " if ok else "FAIL"), label, "->", got if not ok else "")

for mtu in (20, 244):
    da, db, ca, cb = swap("stock", other, "new", mine, mtu)
    check(f"[mtu {mtu}] stock -> modified: both sides finish", (da, db), (True, True))
    check(f"[mtu {mtu}] stock badge receives my card (website ignored)", sorted(ca), ["github", "linkedin", "name"])
    check(f"[mtu {mtu}] modified badge saves the stock card", cb["github"], "ada")

    da, db, ca, cb = swap("new", mine, "stock", other, mtu)
    check(f"[mtu {mtu}] modified -> stock: both sides finish", (da, db), (True, True))

    da, db, ca, cb = swap("new", mine, "new", mine, mtu)
    check(f"[mtu {mtu}] modified <-> modified: website sent", (da, db, ca["website"]), (True, True, "https://christendijoux.com/"))

da, db, ca, cb = swap("stock", phish, "new", mine)
check("malicious card: the other badge still finishes", (da, db), (True, True))
check("malicious card: nothing saved on my side", cb, None)

da, db, ca, cb = swap("stock", mixed, "new", mine)
check("malicious LinkedIn link dropped, GitHub kept", (cb["github"], cb["linkedin"]), ("bob-dev", ""))

v = new_ns
check("GitHub usernames", [v["valid_github"](x) for x in ("Akiyo974", "a-b", "-a", "a--b", "a" * 40, "bad name")],
      [True, True, False, False, False, False])
check("LinkedIn links", [v["valid_linkedin"](x) for x in (
    "https://www.linkedin.com/in/x", "https://ca.linkedin.com/in/x", "https://linkedin.com.evil.io/in/x",
    "https://evil.io/linkedin.com/in/x", "http://www.linkedin.com/in/x", "https://user@linkedin.com/x")],
      [True, True, False, False, False, False])

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
