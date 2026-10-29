# Pedometer

The day's steps, hour by hour, with the distance walked and progress to your goal. The steps come from your watch through [Badger Remote](badger_remote.md): worn around the neck, the badge swings too much to count steps itself.

![Pedometer](../screenshots/pedometer.png)

## Before you start

- A Wear OS watch with **Badger Remote** installed and allowed to read **Physical activity** ([guide](badger_remote.md)).
- Install Pedometer from the **Extensions** tab ([how](README.md#before-you-start-installing-the-apps)).
- Optional: your daily goal with `STEPS_GOAL` in Settings (6,000 by default).

## Using it

1. Open **Badger Remote** on the watch near the badge: it sends the day's steps. Under its buttons, a ✓ shows the badge has them.
2. Open **Pedometer** on the badge.

The screen shows:

- the day's steps in big, with "GitHub Universe '26 · Day 1" or "Day 2" on October 28 and 29, 2026, or the date on other days;
- one square per hour recorded by the watch, brighter with more steps;
- the distance (0.75 m per step) and the progress to your goal;
- when the steps were synced. Before the watch has an hourly history, the screen says "synced 14:32 from Galaxy Watch" instead of the squares.

There are no buttons to learn: use **Home** to leave.

## Good to know

- The badge has no clock: "today" is the day of the last sync. The steps stay on the badge across restarts until the next sync.
- **First day on a Galaxy Watch**: the watch only counts steps from the moment Badger Remote starts listening, so the first total is lower than Samsung Health's. From the next midnight on, it covers the whole day.
- The same steps also feed [Mona Pet](mona_pet.md).

Source: [`system/apps/pedometer`](https://github.com/Akiyo974/badger/tree/main/system/apps/pedometer)
