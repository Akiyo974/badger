"""Simulates the watch's steps reaching the badge, the Pedometer and Mona Pet.

The bytes are the ones the watch app builds (StepsProtocolTest.kt), so a change
on either side that breaks the format shows up here.

Run from the repo root: py tests/test_watch_steps.py
"""
import os
import struct
import sys
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeState:
    """badgeware.State, kept in memory."""

    def __init__(self):
        self.files = {}

    def save(self, name, data):
        self.files[name] = dict(data)

    def load(self, name, data):
        data.update(self.files.get(name, {}))

    def delete(self, name):
        self.files.pop(name, None)


class FakePet:
    def __init__(self, hunger=50, happy=50, clean=50):
        self.values = {"hunger": hunger, "happy": happy, "clean": clean}

    def _change(self, name, amount):
        self.values[name] = max(0, min(100, self.values[name] + amount))
        return self.values[name]

    def hunger(self, amount=0):
        return self._change("hunger", amount)

    def happy(self, amount=0):
        return self._change("happy", amount)

    def clean(self, amount=0):
        return self._change("clean", amount)

    def alive(self):
        return all(self.values.values())


state = FakeState()
badgeware = MagicMock()
badgeware.State = state
sys.modules["badgeware"] = badgeware
sys.modules["bluetooth"] = MagicMock()
for name in ("missing_details", "secrets", "ui"):
    sys.modules[name] = MagicMock()
sys.modules["secrets"] = None  # no secrets.py: the apps use their defaults

BUILTINS = ("badge", "screen", "image", "color", "font", "rect", "shape", "vec2", "HIRES", "LORES", "VSYNC")


def load(path, name):
    ns = {"__name__": name, "run": lambda f: None}
    for builtin in BUILTINS:
        ns[builtin] = MagicMock()
    exec(open(f"{ROOT}/{path}", encoding="utf-8").read(), ns)
    return ns


remote = load("system/remote.py", "remote")
pedometer = load("system/apps/pedometer/__init__.py", "pedometer")
walk = load("system/apps/mona_pet/walk.py", "walk")

# StepsProtocolTest.encodesHeaderThenHours: 4213 steps at 14:32 on 2026-10-28, hours 9 to 11
WATCH_BYTES = bytes([1, 0xEA, 0x07, 10, 28, 14, 32, 0x75, 0x10, 0, 0, 9, 3, 0x2C, 0x01, 0, 0, 0xB0, 0x04])

checks = []


def check(name, ok):
    checks.append(ok)
    print(("OK  " if ok else "FAIL") + " " + name)


# --- remote.py: the steps write ------------------------------------------------
record = remote["parse_steps"](WATCH_BYTES)
check("watch bytes parse", record == {
    "date": [2026, 10, 28], "synced": [14, 32], "steps": 4213, "first_hour": 9, "hours": [300, 0, 1200],
})
check("header only: no hours", remote["parse_steps"](WATCH_BYTES[:11] + bytes([0, 0]))["hours"] == [])
check("hours cut short are dropped", remote["parse_steps"](WATCH_BYTES[:15])["hours"] == [])
check("unknown version is refused", remote["parse_steps"](bytes([2]) + WATCH_BYTES[1:]) is None)
check("too short is refused", remote["parse_steps"](WATCH_BYTES[:5]) is None)
check("impossible date is refused", remote["parse_steps"](WATCH_BYTES[:3] + bytes([13]) + WATCH_BYTES[4:]) is None)
check("buttons still 2 bytes", remote["ACTION_TAP"] == 0 and remote["ACTION_UP"] == 2)

remote["badge"] = MagicMock(uid="5d88b139d7b55fb7")
r = remote["Remote"]()
r.steps_payload = WATCH_BYTES
r._save_steps()
check("saved to /state/watch_steps", state.files.get("watch_steps", {}).get("steps") == 4213)
check("apps see a new sync", r.steps_version == 1)
r.steps_payload = b"junk"
r._save_steps()
check("junk keeps the last steps", state.files["watch_steps"]["steps"] == 4213 and r.steps_version == 1)

# --- Pedometer -------------------------------------------------------------
check("grouped digits", pedometer["grouped"](4213) == "4 213" and pedometer["grouped"](12) == "12"
      and pedometer["grouped"](1234567) == "1 234 567")
check("Universe day 1", pedometer["title"]({"date": [2026, 10, 28]}).endswith("Day 1"))
check("Universe day 2", pedometer["title"]({"date": [2026, 10, 29]}).endswith("Day 2"))
check("after Universe: the date", pedometer["title"]({"date": [2026, 10, 30]}) == "Oct 30")
check("before the first sync", pedometer["title"](None) == "GitHub Universe '26")
many = {"first_hour": 6, "hours": list(range(15))}
check("at most 12 hours, the latest", pedometer["visible_hours"](many) == (9, list(range(3, 15))))
check("synced line", pedometer["synced_line"]({"synced": [9, 5]}) == "synced 09:05 from Galaxy Watch")
check("empty hour is the dimmest square", pedometer["level"](0, 900) is pedometer["LEVELS"][0])
check("busiest hour is the brightest", pedometer["level"](900, 900) is pedometer["LEVELS"][-1])

# --- Mona Pet --------------------------------------------------------------
state.files["watch_steps"] = {"date": [2026, 10, 28], "steps": 4213, "synced": [14, 32], "first_hour": 0, "hours": []}
state.files.pop("mona_pet_walk", None)
pet = FakePet(hunger=10, happy=40)
w = walk["Walk"]()
check("4 213 steps = 8 meals", w.feed(pet) == 8)
check("meals fill her up", pet.hunger() == 100 and pet.happy() == 80)
check("the same steps feed once", w.feed(pet) == 0)
check("a new Mona does not eat them again", walk["Walk"]().feed(FakePet()) == 0)

state.files["watch_steps"]["steps"] = 4480
w.reload()
check("under 4 500: no meal yet", w.feed(FakePet()) == 0)
state.files["watch_steps"]["steps"] = 4520
w.reload()
check("past 4 500: one more meal", w.feed(FakePet()) == 1)

state.files["watch_steps"] = {"date": [2026, 10, 29], "steps": 1000, "synced": [9, 0], "first_hour": 0, "hours": []}
w.reload()
check("a new day starts its meals over", w.feed(FakePet()) == 2)

state.files.pop("watch_steps")
check("no steps, no meals", walk["Walk"]().feed(FakePet()) == 0)

mood = walk["mood"]
check("moods go up with the steps", [mood(n) for n in (0, 600, 2500, 4213, 9000)]
      == ["SLEEPY", "PERKING UP", "HAPPY", "VERY HAPPY", "OVER THE MOON"])

# The format both sides agree on
check("header is 13 bytes", struct.calcsize(remote["STEPS_HEADER"]) == 13)
check("24 hours fit the buffer", 13 + 2 * 24 <= remote["STEPS_BUFFER"])

print()
print(f"{sum(checks)}/{len(checks)} checks passed")
sys.exit(0 if all(checks) else 1)
