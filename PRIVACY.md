# Privacy

Short version: **this project collects nothing.** There are no accounts, no cookies, no analytics and no server of ours. Some apps do talk to other services or to people nearby: they are all listed below.

## The site and Badge Studio

- The pages are static files hosted on GitHub Pages. GitHub may log visits as described in the [GitHub Privacy Statement](https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement).
- To list and install apps, your browser downloads them directly from GitHub (`api.github.com` and `raw.githubusercontent.com`). No other site is contacted.
- Badge Studio talks to your badge over USB with Web Serial, in your browser. Your settings (Wi-Fi, name, contacts) go from your browser to the badge and nowhere else.
- The only thing stored in your browser is the list of extra repositories you added (`localStorage`). Clear the site data to remove it.

## What the badge shares

Some apps share information with people nearby, by design:

| App | What it shares | How to stop it |
|---|---|---|
| Badge (NFC) | Your contact card or website, to any phone that taps the badge. The tag is passive: it stays readable after you leave the app | Set `NFC_CARD = "link"` (website only), then open Badge again and let it rewrite the tag: changing the setting alone leaves the old card on it |
| Radar | Your name and `RADAR_STATUS`, over Bluetooth, to badges around you, while Radar runs | Leave the Radar app |
| Contacts | As soon as the app opens, the badge's id and your name, over Bluetooth, to anything scanning nearby (Radar shows them) | Leave the Contacts app |
| Contacts | Your contact card, over Bluetooth, to the badge you swap with; cards you receive stay on the badge (`tools/export_contacts.ps1` copies them to your PC) | Only while you swap in the Contacts app |
| Badger Remote | Button presses and steps from your watch, over Bluetooth | `WATCH_REMOTE = False` |

## What the badge sends online

Over Wi-Fi, a few apps call other services. Each one sees your network's IP address, and anything in the request:

| App | Service | What it receives |
|---|---|---|
| Badge | GitHub (`github.com`, `api.github.com`) | Your `GITHUB_USERNAME`, to fetch your public profile, contributions and recent activity |
| Badge | [wsrv.nl](https://wsrv.nl) (image resizing) | Your `GITHUB_USERNAME`, in the link of the avatar it resizes |
| ISS | [wheretheiss.at](https://wheretheiss.at) | Nothing about you, just the request for the station's position |

Leave `WIFI_SSID` empty to keep the badge offline.

Apps from other repositories can do anything on the badge: check what they share before installing them.

Questions: open a [discussion](https://github.com/Akiyo974/badger/discussions).
