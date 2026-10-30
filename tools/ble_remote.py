"""Presses the buttons of one or more badges over Bluetooth, from a computer.

The badge's remote.py (started by main.py) offers the same Bluetooth service
Badger Remote, the watch app, uses: each write is 2 bytes, an action then a
button. This script finds the badges nearby and sends them presses, a starting
point for your own projects (a slide clicker, a game controller, a demo that
drives every badge at once). Guide: docs/guides/bluetooth.md

Needs Python 3 and bleak (pip install bleak). From the repo root:
  py tools/ble_remote.py                      lists the badges nearby
  py tools/ble_remote.py select               taps Select on every badge found
  py tools/ble_remote.py --badge 1A2B up up select
  py tools/ble_remote.py --hold 2 right       holds Right for 2 seconds
"""
import argparse
import asyncio
import sys

from bleak import BleakClient, BleakScanner

# system/remote.py
SERVICE_UUID = "6e1d1000-8d5c-4b52-9a57-2a6b4c1b0001"
COMMAND_UUID = "6e1d1001-8d5c-4b52-9a57-2a6b4c1b0001"
TAP, DOWN, UP = 0, 1, 2
BUTTONS = ("up", "down", "left", "right", "select", "back", "home")
# The badge lets go of a held button after 1.5 s without news: repeat DOWN sooner
HOLD_REPEAT_S = 0.5
GAP_S = 0.15


async def find(seconds, wanted):
    """The badges advertising the remote service, as (name, device)."""
    found = await BleakScanner.discover(timeout=seconds, service_uuids=[SERVICE_UUID], return_adv=True)
    badges = []
    for device, adv in found.values():
        name = adv.local_name or device.name or device.address
        if not wanted or name.upper().endswith(wanted.upper()):
            badges.append((name, device))
    return sorted(badges, key=lambda badge: badge[0])


async def press(client, presses, hold):
    for button in presses:
        code = BUTTONS.index(button)
        if hold:
            loop = asyncio.get_running_loop()
            end = loop.time() + hold
            while loop.time() < end:
                await client.write_gatt_char(COMMAND_UUID, bytes((DOWN, code)), response=False)
                # UP goes out at the requested end, not at the next repeat
                await asyncio.sleep(min(HOLD_REPEAT_S, max(0, end - loop.time())))
            await client.write_gatt_char(COMMAND_UUID, bytes((UP, code)), response=False)
        else:
            await client.write_gatt_char(COMMAND_UUID, bytes((TAP, code)), response=False)
        await asyncio.sleep(GAP_S)


async def drive(name, device, presses, hold):
    try:
        async with BleakClient(device) as client:
            await press(client, presses, hold)
        print(f"{name}: {' '.join(presses)}")
    except Exception as error:  # one badge failing must not stop the others
        print(f"{name}: {error}", file=sys.stderr)


async def main():
    parser = argparse.ArgumentParser(description="Press the buttons of badges nearby over Bluetooth.")
    parser.add_argument("buttons", nargs="*", choices=BUTTONS, metavar="button", help=" ".join(BUTTONS))
    parser.add_argument("--badge", help="only the badge whose name ends with this, e.g. 1A2B")
    parser.add_argument("--hold", type=float, metavar="SECONDS", help="hold each button this long instead of a tap")
    parser.add_argument("--scan", type=float, default=5, metavar="SECONDS", help="how long to look for badges (5)")
    args = parser.parse_args()

    badges = await find(args.scan, args.badge)
    if not badges:
        sys.exit("No badge found. Is it on, near the computer, and on the menu or an app that leaves Bluetooth free?")
    if not args.buttons:
        for name, device in badges:
            print(f"{name}  ({device.address})")
        return
    # Every badge at once: each one accepts a single connection, the computer holds several
    await asyncio.gather(*(drive(name, device, args.buttons, args.hold) for name, device in badges))


if __name__ == "__main__":
    asyncio.run(main())
