# Contacts

Swap contact cards by holding two badges back to back: name, GitHub, LinkedIn and website. Each card you receive can be shown as a QR code, so anyone can scan it with a phone.

![Contacts](../screenshots/contacts.png)

## Before you start

- Set your details in the Settings tab of Badge Studio: `CONTACT_NAME`, `GITHUB_USERNAME`, `CONTACT_LINKEDIN`, `CONTACT_WEBSITE`.
- Install it from the **Extensions** tab ([how](README.md#before-you-start-installing-the-apps)). It replaces the stock Contacts app and stays compatible with it: you can swap with any badge, modified or not (stock badges simply ignore the website).

## Swapping cards

1. Both people open **Contacts**.
2. Hold the two badges **back to back**.
3. When they see each other, an offer appears. Press **Select** to swap, or **←** for *no thanks*. The offer expires after 15 seconds.
4. When both have accepted, the cards are exchanged and the new contact is saved.

Received links are checked before they are kept: a card with no valid link is refused.

## Your contacts

| Where | Button | What it does |
|---|---|---|
| Home | **Select** | Open the list of contacts |
| Home | **Back** | Leave the app |
| List | **↑ / ↓** (or **→**) | Choose a contact |
| List | **Select** | Open their card |
| List | **←** | Back home |
| Card | **→** | Next link (GitHub, LinkedIn, website) as a QR code |
| Card | **↓** | Delete this contact |
| Card | **←** | Back to the list |
| Delete? | **Select** / **←** | Delete / keep |

Up to 200 contacts are kept, in `/state` on the badge.

## Taking your contacts home

On Windows, `./tools/export_contacts.ps1` (from a clone of the repo, badge plugged in) writes `contacts.csv` and `contacts.vcf`. The vCard file imports straight into a phone, Outlook or Google Contacts.

## Good to know

- While Contacts is open, the badge announces its id and your name over Bluetooth; leave the app to stop. See [Privacy](https://github.com/Akiyo974/badger/blob/main/PRIVACY.md).
- Badges running Contacts also show up on [Radar](radar.md).
- The [watch remote](badger_remote.md) does not work inside Contacts, which needs the badge's Bluetooth.

Source: [`system/apps/contacts`](https://github.com/Akiyo974/badger/tree/main/system/apps/contacts)
