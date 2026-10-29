# Privacy

Short version: **nothing is collected.** There are no accounts, no cookies, no analytics and no server of ours.

## The site and Badge Studio

- The pages are static files hosted on GitHub Pages. GitHub may log visits as described in the [GitHub Privacy Statement](https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement).
- To list and install apps, your browser downloads them directly from GitHub (`api.github.com` and `raw.githubusercontent.com`). No other site is contacted.
- Badge Studio talks to your badge over USB with Web Serial, in your browser. Your settings (Wi-Fi, name, contacts) go from your browser to the badge and nowhere else.
- The only thing stored in your browser is the list of extra repositories you added (`localStorage`). Clear the site data to remove it.

## What the badge shares

Some apps share information with people nearby, by design:

| App | What it shares | How to stop it |
|---|---|---|
| Badge (NFC) | Your contact card or website, to any phone that taps the badge | `NFC_CARD = "link"` shares the website only |
| Radar | Your name and `RADAR_STATUS`, over Bluetooth, to badges around you, while Radar runs | Leave the Radar app |
| Contacts | Your contact card, over Bluetooth, to the badge you swap with; cards you receive stay on the badge (`tools/export_contacts.ps1` copies them to your PC) | Only while you swap in the Contacts app |
| Badger Remote | Button presses and steps from your watch, over Bluetooth | `WATCH_REMOTE = False` |

Apps from other repositories can do anything on the badge: check what they share before installing them.

Questions: open a [discussion](https://github.com/Akiyo974/badger/discussions).
