# Bluetooth from a computer

Press the badge's buttons from a computer, on one badge or several at once, and build your own project on top: a slide clicker, a game controller, a booth demo that drives every badge in the room.

It uses the same Bluetooth service as the [Badger Remote](badger_remote.md) watch app. Installing apps, settings and screenshots stay on USB with [Badge Studio](https://akiyo974.github.io/badger/studio/).

## Before you start

- The badge runs this repo's `main.py` and `remote.py` (installed by `tools/deploy.ps1`, or the **Repair** tab of Badge Studio with *Factory + the changes of Akiyo974/badger*).
- The badge is on the menu or in an app that leaves Bluetooth free: not Contacts, Pong, Merge Conflict or Radar.
- `WATCH_REMOTE` is not set to `False` in Settings.
- Each badge shows up as **Badger XXXX** (the end of its id). It accepts one connection at a time: close Badger Remote on your watch first.

## In the browser: Badge Remote

Open **[Badge Remote](examples/remote.html)** in Chrome or Edge (Windows, macOS, ChromeOS or Android; not Firefox or Safari).

1. Press **Add a badge** and pick it in the list. Repeat for each badge.
2. Press the on-screen buttons, or use the keyboard: arrows, **Enter** for Select, **Backspace** for Back, **H** for Home.
3. Untick a badge to leave it out. A short press is a tap; keep it down to hold the button.

It is one HTML file: copy [`docs/guides/examples/remote.html`](https://github.com/Akiyo974/badger/blob/main/docs/guides/examples/remote.html) to start your own page.

## From a script: Python

Install [bleak](https://pypi.org/project/bleak/) once with `pip install bleak`, then from the repo root:

```
py tools/ble_remote.py                         # list the badges nearby
py tools/ble_remote.py select                  # tap Select on every badge found
py tools/ble_remote.py --badge 1A2B up up select
py tools/ble_remote.py --hold right 2          # hold Right for 2 seconds
```

[`tools/ble_remote.py`](https://github.com/Akiyo974/badger/blob/main/tools/ble_remote.py) works on Windows, macOS and Linux and drives every badge it finds at once.

## Build your own

The whole protocol fits in a table. Connect to the badge, find the service, and write 2 bytes to the command characteristic:

| | |
|---|---|
| Service | `6e1d1000-8d5c-4b52-9a57-2a6b4c1b0001` |
| Command characteristic | `6e1d1001-8d5c-4b52-9a57-2a6b4c1b0001`, write without response |
| Byte 1: action | `0` tap, `1` down, `2` up |
| Byte 2: button | `0` ↑, `1` ↓, `2` ←, `3` →, `4` Select, `5` Back, `6` Home |

- A **tap** presses and releases on the next frame.
- A held button (**down**) is let go after 1.5 s without news: send **down** again every 0.5 s while holding, then **up**.
- Apps see these presses exactly like the real buttons, so any app works with them, yours included.

In JavaScript (Web Bluetooth), tapping Select:

```js
const device = await navigator.bluetooth.requestDevice({ filters: [{ services: ["6e1d1000-8d5c-4b52-9a57-2a6b4c1b0001"] }] });
const service = await (await device.gatt.connect()).getPrimaryService("6e1d1000-8d5c-4b52-9a57-2a6b4c1b0001");
const command = await service.getCharacteristic("6e1d1001-8d5c-4b52-9a57-2a6b4c1b0001");
await command.writeValueWithoutResponse(new Uint8Array([0, 4]));
```

A second characteristic, `6e1d1002-…`, takes the day's steps for [Pedometer](pedometer.md) and [Mona Pet](mona_pet.md): its format is `STEPS_HEADER` in [`system/remote.py`](https://github.com/Akiyo974/badger/blob/main/system/remote.py).

## Several badges

The computer can hold several connections at once, often around 5 to 7, depending on its Bluetooth chip. Badge Remote and `ble_remote.py` both send each press to every connected badge. Over USB, Badge Studio works one badge per tab.

## Good to know

- There is **no pairing**: anyone nearby with the page or the script can press your buttons while the remote is on. `WATCH_REMOTE = False` in Settings turns it off.
- No badge in the list? Go back to the menu (another app may hold Bluetooth), move closer, and check nothing else is connected to it.

Source: [`system/remote.py`](https://github.com/Akiyo974/badger/blob/main/system/remote.py) (badge), [`docs/guides/examples/remote.html`](https://github.com/Akiyo974/badger/blob/main/docs/guides/examples/remote.html) and [`tools/ble_remote.py`](https://github.com/Akiyo974/badger/blob/main/tools/ble_remote.py) (computer).
