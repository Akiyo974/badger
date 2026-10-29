# Menu

The badge's home screen, reorganised: the apps made or changed in this repo first, the stock ones after, the apps installed from the store in their own band, and a little surprise when you shake the badge.

![The menu with the CUSTOM band](../screenshots/menu.png)

## Before you start

Install it from the **Extensions** tab ([how](README.md#before-you-start-installing-the-apps)), **before the other apps**: the stock menu does not show the apps installed from the store.

## The bands

| Band | What is in it |
|---|---|
| **CUSTOM** | The apps of this repo: Badge, Contacts, Radar, Duck Maze, Pedometer, Mona Pet… |
| **STOCK** | The other apps that came with the badge |
| **INSTALLED** | Apps installed from the **Apps** tab of Badge Studio (they live in `/apps`) |

Apps without a built-in icon show their own `icon.png`.

## Arrange it from Badge Studio

In the **Home screen** tab of Badge Studio (badge connected): drag the apps into the order you want, choose which ones go under **CUSTOM**, and hide the others. **Save and reboot** writes the layout to the badge; **Back to the default layout** undoes your changes.

## Shake the badge

On the menu, shake the badge: Mona gets dizzy, with X eyes and rubber ducks circling her head, for a few seconds. Any button closes it without opening an app. Two or three taps are not enough: it takes a real shake.

![Dizzy Mona](../screenshots/menu-dizzy.png)

Source: [`system/apps/menu`](https://github.com/Akiyo974/badger/tree/main/system/apps/menu)
