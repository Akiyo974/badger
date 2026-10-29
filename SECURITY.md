# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Report it privately instead, through [GitHub private vulnerability reporting](https://github.com/Akiyo974/badger/security/advisories/new) (Security tab → *Report a vulnerability*). If that form isn't available, open a [discussion](https://github.com/Akiyo974/badger/discussions) asking for a private contact, without the details.

Include what you found, how to reproduce it, and what it could let someone do. You should get an answer within a week. Once a fix is out, you'll be credited in the advisory and the [changelog](CHANGELOG.md) unless you'd rather stay anonymous.

## Supported versions

Only the latest code on `main` (and the live [Badge Studio](https://akiyo974.github.io/badger/studio/)) gets fixes.

## What counts

- Badge Studio or the site running code or reading data it shouldn't (for example, an app from a repository making Badge Studio leak the badge's Wi-Fi password)
- Apps in `system/apps/` that expose personal data over Bluetooth, NFC or Wi-Fi beyond what their README says
- Secrets or personal data committed by mistake

Bugs in the stock MonaOS firmware or the official apps belong to their authors: report those to [badger/home](https://github.com/badger/home).

## Credentials and personal settings

- Your settings (Wi-Fi password, name, LinkedIn, etc.) live in `system/secrets.py` **on the badge**. That file is in `.gitignore`: never commit it, and never paste it into an issue or pull request. Use [`secrets.example.py`](secrets.example.py) as the template.
- Badge Studio never reads the Wi-Fi password back from the badge: it only learns whether one is set.
- No API key, token or account is needed by this repository, Badge Studio or CI. If a pull request asks you to add one, something is wrong.
- **Apps run with full access to the badge.** Badge Studio installs code from GitHub repositories; only install apps from repositories you trust, and read an app's code before installing it from someone's fork.
