"""Turns the badge into a game pad for this computer, over the USB cable.

The badge's Controller app prints one line per press on its serial port:
"+up" when a button goes down, "-up" when it is let go (up, down, left,
right, select, back). This script reads them and presses the matching keys,
so the badge drives any game or program. Guide: docs/guides/controller.md

Needs Python 3, pyserial and pynput (pip install pyserial pynput). From the
repo root, with the badge plugged in and Controller open:
  py tools/badge_controller.py                         arrows, Space, Escape
  py tools/badge_controller.py --map select=z back=x   your own keys
  py tools/badge_controller.py --print                 only print the presses

In your own Python program:
  from badge_controller import events
  for event in events():
      if event is None:
          continue  # unplugged: it reconnects by itself
      pressed, button = event
      print(button, "down" if pressed else "up")
"""
import argparse
import re
import sys
import time

# The badge's USB ids (Badge Studio uses the same)
VID, PID = 0x2E8A, 0x1101
BUTTONS = ("up", "down", "left", "right", "select", "back")
LINE = re.compile(r"^([+-])(%s)$" % "|".join(BUTTONS))
DEFAULT_MAP = {"up": "up", "down": "down", "left": "left", "right": "right", "select": "space", "back": "esc"}
RETRY_S = 2


def parse_line(line):
    """(pressed, button) for a Controller line, None for anything else on the port."""
    match = LINE.match(line.strip())
    return (match.group(1) == "+", match.group(2)) if match else None


def parse_map(pairs):
    """The key for each button, from DEFAULT_MAP and button=key pairs."""
    mapping = dict(DEFAULT_MAP)
    for pair in pairs:
        button, _, key = pair.partition("=")
        if button not in BUTTONS or not key:
            raise ValueError(f"{pair}: expected button=key, button one of {', '.join(BUTTONS)}")
        mapping[button] = key
    return mapping


def find_port():
    from serial.tools import list_ports

    for port in list_ports.comports():
        if port.vid == VID and port.pid == PID:
            return port.device
    return None


def events(port=None):
    """Yields (pressed, button) from the badge, reconnecting when it is unplugged."""
    import serial

    while True:
        device = port or find_port()
        if not device:
            print("Waiting for the badge on USB…", file=sys.stderr)
            time.sleep(RETRY_S)
            continue
        try:
            with serial.Serial(device, 115200, timeout=1) as link:
                print(f"Connected to the badge on {device}. Open Controller on it.", file=sys.stderr)
                while True:
                    event = parse_line(link.readline().decode("utf-8", "replace"))
                    if event:
                        yield event
        except serial.SerialException as error:
            print(f"Badge disconnected ({error}).", file=sys.stderr)
            yield None  # lets the caller let go of every key
            time.sleep(RETRY_S)


def key_for(name):
    """A pynput key: a named key (space, esc, enter, up…) or a single character."""
    from pynput.keyboard import Key, KeyCode

    if len(name) == 1:
        return KeyCode.from_char(name)
    try:
        return getattr(Key, name)
    except AttributeError:
        raise ValueError(f"{name}: not a key (try a letter, or space, enter, esc, tab, up, f1…)") from None


def main():
    parser = argparse.ArgumentParser(description="Use the badge as a game pad for this computer.")
    parser.add_argument("--map", nargs="+", default=[], metavar="BUTTON=KEY",
                        help="change keys, e.g. select=z back=x (keys: a letter, or space, enter, esc, up, f1…)")
    parser.add_argument("--print", action="store_true", help="print the presses instead of pressing keys")
    parser.add_argument("--port", help="the badge's serial port, if it is not found by itself")
    args = parser.parse_args()
    try:
        mapping = parse_map(args.map)
    except ValueError as error:
        parser.error(str(error))

    if args.print:
        for event in events(args.port):
            if event:
                print(("+" if event[0] else "-") + event[1], flush=True)
        return

    from pynput.keyboard import Controller

    try:
        keys = {button: key_for(name) for button, name in mapping.items()}
    except ValueError as error:
        parser.error(str(error))
    keyboard = Controller()
    down = set()  # badge buttons held

    def key_held(button):
        # Two buttons may share a key: it stays down while either one is held
        return any(keys[other] == keys[button] for other in down if other != button)

    print("Badge buttons:", ", ".join(f"{b} → {mapping[b]}" for b in BUTTONS), file=sys.stderr)
    try:
        for event in events(args.port):
            if event is None:
                # Unplugged: never leave a key stuck down
                for key in {keys[button] for button in down}:
                    keyboard.release(key)
                down.clear()
                continue
            pressed, button = event
            if pressed and button not in down:
                if not key_held(button):
                    keyboard.press(keys[button])
                down.add(button)
            elif not pressed and button in down:
                down.discard(button)
                if not key_held(button):
                    keyboard.release(keys[button])
    except KeyboardInterrupt:
        pass
    finally:
        for key in {keys[button] for button in down}:
            keyboard.release(key)


if __name__ == "__main__":
    main()
