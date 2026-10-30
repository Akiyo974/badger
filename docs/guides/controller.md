# Controller

Use the badge as a game pad for your computer. Its ↑ ↓ ← →, Select and Back become key presses in any game or program, over the USB cable. Or read them in your own code for a project.

## Before you start

- Install **Controller** from the **Extensions** tab of Badge Studio ([how](README.md#before-you-start-installing-the-apps)).
- On the computer: Python 3 and a clone of this repo, then once: `pip install pyserial pynput`.

## Play with it

1. Plug the badge into the computer with the USB cable and open **Controller** on it.
2. From the repo root, run:

   ```
   py tools/badge_controller.py
   ```

3. Switch to your game or program. The badge's buttons now press these keys:

| Badge | Key |
|---|---|
| **↑ ↓ ← →** | Arrow keys |
| **Select** | Space |
| **Back** | Escape |

Holding a button holds the key. Stop with **Ctrl+C**. **Home** on the badge leaves the app.

## Your own keys

Pick the key for any button with `--map`: a letter, or a named key (`space`, `enter`, `esc`, `tab`, `up`, `f1`…).

```
py tools/badge_controller.py --map select=z back=x
py tools/badge_controller.py --map up=w down=s left=a right=d
```

## Use it in your own project

Every press is one line on the badge's serial port: `+up` when it goes down, `-up` when it is let go (`up`, `down`, `left`, `right`, `select`, `back`). Three ways to use them:

- **See them**: `py tools/badge_controller.py --print` prints each line instead of pressing keys.
- **In Python**: copy [`tools/badge_controller.py`](https://github.com/Akiyo974/badger/blob/main/tools/badge_controller.py) next to your program, then:

  ```python
  from badge_controller import events

  for event in events():
      if event is None:
          continue  # the badge was unplugged; it reconnects by itself
      pressed, button = event
      if pressed and button == "select":
          print("Fire!")
  ```

- **In any language**: open the badge's serial port (115200 baud; on Windows a `COM` port, on macOS `/dev/cu.usbmodem…`, on Linux `/dev/ttyACM0`) and read lines. Ignore the lines that do not start with `+` or `-`.

## Good to know

- The script finds the badge by its USB ids. If it does not, pass the port: `--port COM5`.
- Only one program can open the serial port at a time: close Badge Studio's Console tab and Thonny first.
- The key presses go to the window in front, like a real keyboard. On macOS, allow your terminal under **System Settings → Privacy & Security → Accessibility**.
- Presses from the [Badger Remote](badger_remote.md) watch go through too: the watch can drive the computer through the badge.
- Want it the other way round, the computer pressing the badge's buttons? See [Bluetooth from a computer](bluetooth.md).

Source: [`system/apps/controller`](https://github.com/Akiyo974/badger/tree/main/system/apps/controller) (badge) and [`tools/badge_controller.py`](https://github.com/Akiyo974/badger/blob/main/tools/badge_controller.py) (computer).
