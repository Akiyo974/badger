# Badge

Your name badge, upgraded: your GitHub profile and contribution graph, QR codes to your site, LinkedIn and GitHub, a "Last push" line, and, with optional add-ons, an NFC contact card and the graph on an LED matrix.

![The Badge app: GitHub profile and contribution graph](../screenshots/badge.png)

## Before you start

- **Wi-Fi** (2.4 GHz only) and your **GitHub username**: `WIFI_SSID`, `WIFI_PASSWORD` and `GITHUB_USERNAME` in the Settings tab of Badge Studio. Without them, the app shows what is missing.
- **Your details** for the contact card: `CONTACT_NAME`, `CONTACT_LINKEDIN`, `CONTACT_WEBSITE`, and optionally `CONTACT_TITLE` and `CONTACT_COMPANY`.
- Install it from the **Extensions** tab ([how](README.md#before-you-start-installing-the-apps)). It replaces the stock Badge app; the old one is backed up.

## Using it

Open **Badge** from the menu and wait a few seconds: your profile, contribution graph and recent public activity download over Wi-Fi.

| Button | What it does |
|---|---|
| **↓** | Next QR code page: website, LinkedIn, GitHub, then back to the profile |
| **↑** | Previous page |
| **← and →** held together | Download your profile again |

![QR code page](../screenshots/badge-qr.png)

## NFC contact card (optional)

With an **Adafruit ST25DV** NFC tag on the Qw/ST port, the app writes your contact card to it when it starts. Anyone who holds a phone near the antenna is offered to add you as a contact: name, title, company, and labelled Website, LinkedIn and GitHub links.

- `NFC_CARD = "link"` puts only your website on the tag instead of the whole card.
- The tag is passive: it stays readable after you leave the app. After changing `NFC_CARD`, open Badge again so it rewrites the tag.
- While Badge is open, it notices each scan: Mona appears with hearts and "thanks for the scan!", and a counter goes up.

![Thanks for the scan](../screenshots/badge-scan.png)

The tag must be NDEF-formatted (as Adafruit ships it). Any data already on it is replaced.

## LED matrix and vibration (optional)

- **13×9 RGB matrix (IS31FL3741)**: the last 13 weeks of your graph in green, with the weekly total on the bottom row. A blue dot sweeps the top row while loading; amber means missing settings, red a connection error.
- **DRV2605 haptic driver** with a vibration motor: a buzz on each NFC scan.

Both are optional and can be plugged in or out between launches.

## Make it yours

The QR codes point to the author's pages. To put yours, change the links in `TARGETS` of [`tools/make_qr.py`](https://github.com/Akiyo974/badger/blob/main/tools/make_qr.py), run `py tools/make_qr.py system/apps/badge`, and update the captions in `QR_PAGES` of `system/apps/badge/__init__.py`.

## Troubleshooting

- **"missing details"**: set the Wi-Fi and GitHub username in Settings, then restart the badge.
- **Red dot on the matrix, or no graph**: the badge could not reach GitHub. Check the network is 2.4 GHz and the password.
- **Phones don't react to the tag**: check the tag is NDEF-formatted; the Console tab of Badge Studio says why it was left untouched.

Source: [`system/apps/badge`](https://github.com/Akiyo974/badger/tree/main/system/apps/badge)
