"""Checks the badge as a game pad: the Controller app prints a line per press
and release, and tools/badge_controller.py turns those lines into key presses,
letting go of every key when the badge is unplugged. No badge, serial port or
keyboard is needed: they are simulated.

Run from the repo root: py tests/test_controller.py
"""
import contextlib
import io
import os
import sys
import types
import unittest
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.modules.setdefault("missing_details", MagicMock())

import badge_controller  # noqa: E402

NAMES = ("UP", "DOWN", "LEFT", "RIGHT", "SELECT", "BACK")


class FakeBadge:
    def __init__(self):
        self.down = set()

    def held(self, button):
        return button in self.down

    def mode(self, flags):
        pass


def load_app():
    badge = FakeBadge()
    ns = {"__name__": "controller", "run": lambda f: None, "badge": badge}
    for name in ("screen", "image", "color", "shape", "HIRES", "VSYNC"):
        ns[name] = MagicMock()
    ns["screen"].measure_text.return_value = (10, 10)
    for name in NAMES:
        ns["BUTTON_" + name] = "BUTTON_" + name
    with open(os.path.join(ROOT, "system", "apps", "controller", "__init__.py"), encoding="utf-8") as file:
        exec(file.read(), ns)
    return ns, badge


def frame(ns, badge, *down):
    badge.down = {"BUTTON_" + name for name in down}
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ns["update"]()
    return out.getvalue().split()


class ControllerAppTest(unittest.TestCase):
    def test_lines_on_press_and_release_only(self):
        ns, badge = load_app()
        self.assertEqual(frame(ns, badge), [])
        self.assertEqual(frame(ns, badge, "UP"), ["+up"])
        self.assertEqual(frame(ns, badge, "UP"), [])  # held: nothing new
        self.assertEqual(frame(ns, badge, "UP", "SELECT"), ["+select"])
        self.assertEqual(frame(ns, badge, "SELECT"), ["-up"])
        self.assertEqual(frame(ns, badge), ["-select"])
        self.assertEqual(ns["presses"], 2)

    def test_every_line_is_understood_by_the_computer(self):
        ns, badge = load_app()
        lines = frame(ns, badge, *NAMES) + frame(ns, badge)
        events = [badge_controller.parse_line(line) for line in lines]
        self.assertEqual(len(events), 12)
        self.assertTrue(all(events))
        self.assertEqual({button for _, button in events}, set(badge_controller.BUTTONS))


class ParseTest(unittest.TestCase):
    def test_lines(self):
        self.assertEqual(badge_controller.parse_line("+left\r\n"), (True, "left"))
        self.assertEqual(badge_controller.parse_line("-back"), (False, "back"))
        for noise in ("", "remote: radio unavailable", "+jump", ">>> ", "up"):
            self.assertIsNone(badge_controller.parse_line(noise))

    def test_map(self):
        mapping = badge_controller.parse_map(["select=z", "back=x"])
        self.assertEqual((mapping["select"], mapping["back"], mapping["up"]), ("z", "x", "up"))
        with self.assertRaises(ValueError):
            badge_controller.parse_map(["jump=z"])
        with self.assertRaises(ValueError):
            badge_controller.parse_map(["select="])


class KeysTest(unittest.TestCase):
    def run_main(self, stream, *args):
        """The keys main() presses and releases for these badge events."""
        log = []

        class Keyboard:
            def press(self, key):
                log.append(("press", key))

            def release(self, key):
                log.append(("release", key))

        class Key:
            up, down, left, right, space, esc = "UP", "DOWN", "LEFT", "RIGHT", "SPACE", "ESC"

        keyboard = types.ModuleType("pynput.keyboard")
        keyboard.Controller, keyboard.Key = Keyboard, Key
        keyboard.KeyCode = types.SimpleNamespace(from_char=lambda c: "char:" + c)
        sys.modules["pynput"] = types.ModuleType("pynput")
        sys.modules["pynput.keyboard"] = keyboard
        original = badge_controller.events
        badge_controller.events = lambda port=None: iter(stream)
        sys.argv = ["badge_controller.py", *args]
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                badge_controller.main()
        finally:
            badge_controller.events = original
        return log

    def test_two_buttons_on_one_key(self):
        stream = [(True, "up"), (True, "select"), (False, "up"), (False, "select")]
        log = self.run_main(stream, "--map", "up=z", "select=z")
        self.assertEqual(log, [("press", "char:z"), ("release", "char:z")])

    def test_keys_follow_the_badge_and_are_let_go_when_unplugged(self):
        log = []

        class Keyboard:
            def press(self, key):
                log.append(("press", key))

            def release(self, key):
                log.append(("release", key))

        class Key:
            up, down, left, right, space, esc = "UP", "DOWN", "LEFT", "RIGHT", "SPACE", "ESC"

        keyboard = types.ModuleType("pynput.keyboard")
        keyboard.Controller, keyboard.Key = Keyboard, Key
        keyboard.KeyCode = types.SimpleNamespace(from_char=lambda c: "char:" + c)
        sys.modules["pynput"] = types.ModuleType("pynput")
        sys.modules["pynput.keyboard"] = keyboard

        stream = [(True, "up"), (True, "select"), (False, "up"), None, (True, "back"), (False, "back")]
        original = badge_controller.events
        badge_controller.events = lambda port=None: iter(stream)
        sys.argv = ["badge_controller.py", "--map", "back=x"]
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                badge_controller.main()
        finally:
            badge_controller.events = original
        self.assertEqual(log, [
            ("press", "UP"), ("press", "SPACE"), ("release", "UP"),
            ("release", "SPACE"),  # unplugged with Select down
            ("press", "char:x"), ("release", "char:x"),
        ])


if __name__ == "__main__":
    unittest.main()
