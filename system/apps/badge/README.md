# Badge

Display your GitHub profile and contribution graph.

## Requirements

This app needs internet access. Add your Wi-Fi details and your GitHub username (`GITHUB_USERNAME`) to `secrets.py` on the badge before using it, or enter them with the Settings app.

## Usage

Launch the app and wait for your profile and contribution graph to download.

When an IS31FL3741 13×9 RGB matrix is connected to the Qw/ST I²C port at address `0x30`, it shows the latest 13 weeks of your contribution graph in green. While data loads, a blue point sweeps across the top row; missing settings show amber and connection errors show red. Matrix brightness uses a limited global-current setting, and the previous driver values are restored when the app exits.

An Adafruit ST25DV NFC tag connected to the same I²C port is programmed with `https://christendijoux.com` when the app starts. Hold a phone close to the tag antenna to open the site; the link stays on the passive tag after leaving the app. Existing tag data is replaced with this link. The tag must already be NDEF-formatted (Type 5 capability container, as Adafruit ships it); otherwise the app leaves it untouched and prints why in the serial console.

QR pages and recent public activity remain available.
