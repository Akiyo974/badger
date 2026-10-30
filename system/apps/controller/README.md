# Controller

The badge as a game pad for your computer: ↑ ↓ ← →, Select and Back become key presses in any game or program, over the USB cable.

Plug the badge in, open **Controller**, then on the computer run `py tools/badge_controller.py` (from a clone of the repo, with `pip install pyserial pynput`). Guide: [docs/guides/controller.md](https://github.com/Akiyo974/badger/blob/main/docs/guides/controller.md).

Each press is also printed on the serial port as `+up` / `-up`, so your own program can read it.
