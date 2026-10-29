# Radar

See the badges around you as dots on a radar, find out who they are, and play **Hot / Cold** to track one down in a crowd.

![Radar](../screenshots/radar.png)

## Before you start

- Install it from the **Extensions** tab ([how](README.md#before-you-start-installing-the-apps)).
- Your name on other people's radars is `CONTACT_NAME` (or the badge's own name). Add a short status with `RADAR_STATUS`, like "Ask me about MicroPython". Name and status share 25 bytes.

## Reading the radar

- Rings are labelled **Very near**, **Near** and **Far**. They come from the Bluetooth signal strength, **not a distance in metres**: bodies, walls and how the badge is turned all change it.
- A dot's angle is a fixed spot picked from the badge's id, **not a direction**.
- You see every badge running Radar, and stock badges while they are in Contacts, Pong or Merge Conflict (their Bluetooth is only on then). Only badges are shown, never phones.
- A badge not heard for 4 seconds **fades**; after 12 seconds it disappears. It comes back as soon as it is heard again.

## Controls

| View | Button | What it does |
|---|---|---|
| Radar | **Select** | Open the list of nearby badges |
| Radar | **→** | Open the encounter history |
| List | **↑ / ↓** | Choose a badge |
| List | **→** | Play Hot / Cold with that badge |
| List | **Select** / **←** | Back to the radar |
| Hot / Cold | **Select** | You found them: **Found!** with your time |
| Hot / Cold | **←** | Quit the game |
| History | **↑ / ↓** | Scroll |
| History | **Select** / **←** | Back to the radar |

![The list of nearby badges](../screenshots/radar-list.png)

## Hot / Cold

Pick a badge in the list and press **→**. A gauge, **Cold / Warm / Hot** and a **Warmer / Colder / Steady** trend follow that badge's signal, and the case lights (and the optional matrix and motor) follow only that badge. Walk around until it is hot, then find the person and press **Select** yourself: the game never decides you won from the signal alone. If the badge goes quiet, the game waits for that same badge.

![Hot / Cold](../screenshots/radar-game.png)

## Encounter history

**→** on the radar lists the 200 most recent distinct badges seen, with their name, status and how many times they came by. It is kept across restarts. It records detections, not meetings: use [Contacts](contacts.md) to swap details.

![Encounter history](../screenshots/radar-history.png)

## Optional hardware

- **13×9 RGB matrix (IS31FL3741)**: a small radar with the sweep and the badges, coloured by app (blue Radar, yellow Contacts, orange Pong).
- **DRV2605 haptic driver** with a vibration motor: a short buzz when a badge arrives; in Hot / Cold, pulses that speed up as you get closer.

## Good to know

- While Radar runs, your name and status are broadcast to badges around you. Leave the app to stop. See [Privacy](https://github.com/Akiyo974/badger/blob/main/PRIVACY.md).
- The [watch remote](badger_remote.md) does not work inside Radar, which needs the badge's Bluetooth.

More detail: [Radar's README](https://github.com/Akiyo974/badger/blob/main/system/apps/radar/README.md). Source: [`system/apps/radar`](https://github.com/Akiyo974/badger/tree/main/system/apps/radar)
