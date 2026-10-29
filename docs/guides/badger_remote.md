# Badger Remote

A Wear OS watch app that becomes the badge's buttons: ↑ ↓ ← →, Select, Back and Home, in every app and in the menu. It also sends the day's steps to the badge for [Pedometer](pedometer.md) and [Mona Pet](mona_pet.md).

![Badger Remote moving through the badge menu](../media/badger-remote.gif)

## Before you start

- A **Wear OS** watch (Galaxy Watch 4 or newer) and a computer with `adb` ([Android platform tools](https://developer.android.com/tools/releases/platform-tools)).
- The badge runs this repo's `main.py` and `remote.py`, which start the remote. Installing the apps from this repo with `tools/deploy.ps1` puts them in place; the **Repair** tab of Badge Studio with *Factory + the changes of Akiyo974/badger* does too.

## Installing the watch app

1. Download the APK: the **badger-remote-debug** artifact of the latest [CI run](https://github.com/Akiyo974/badger/actions/workflows/ci.yml) (sign in to GitHub; it is a zip holding `app-debug.apk`).
2. On the watch: **Settings → About watch → Software information**, tap **Software version** 7 times. Then in **Settings → Developer options**, turn on **ADB debugging** and **Wireless debugging**. The watch and the computer must be on the same Wi-Fi.
3. In **Wireless debugging**, tap **Pair new device**, then on the computer:

   ```
   adb pair 192.168.1.42:37000      # IP:port of the pairing screen, then the code
   adb connect 192.168.1.42:41000   # IP:port at the top of Wireless debugging
   adb install -r app-debug.apk
   ```

4. Open **Badger Remote** on the watch and allow **Nearby devices** (and **Physical activity** for the steps).

If `adb install` answers `INSTALL_FAILED_UPDATE_INCOMPATIBLE`, run `adb uninstall com.christendijoux.badgerremote` first.

## Using it

- Switch the badge on near the watch: its name (`Badger` + the end of its id) appears at the top and the buttons light up. The watch remembers it; tap the name to pick another badge.
- **Tap** a button for a short press; **keep your finger on it** to hold (e.g. to zoom in ISS). The **crown** scrolls like ↑ / ↓.
- Under the buttons: the day's steps, with ✓ once the badge has them.

## Good to know

- It does not work inside **Contacts, Pong, Merge Conflict and Radar**: they need the badge's Bluetooth. The watch reconnects by itself when you leave them.
- **No pairing**: anyone nearby with the app could press your buttons while the remote is on. `WATCH_REMOTE = False` in Settings turns it off.

Source: [`wear/`](https://github.com/Akiyo974/badger/tree/main/wear) (watch) and [`system/remote.py`](https://github.com/Akiyo974/badger/blob/main/system/remote.py) (badge). Protocol details are in the [README](https://github.com/Akiyo974/badger#watch-remote-wear-os).
