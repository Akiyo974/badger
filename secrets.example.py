# Copy this file to system/secrets.py on the badge (USB drive) and fill it in.
# The badge supports a single Wi-Fi network, 2.4 GHz only.
WIFI_SSID = "my-wifi"
WIFI_PASSWORD = "my-password"
GITHUB_USERNAME = "Akiyo974"
CONTACT_NAME = "Christen Dijoux"
CONTACT_LINKEDIN = "christen-dijoux"  # username or full link
CONTACT_WEBSITE = "christendijoux.com"  # added by this repo; ignored by stock badges
CONTACT_TITLE = "Specialist in digital innovation"  # NFC contact card only
CONTACT_COMPANY = "Gagnon Frères"  # NFC contact card only
NFC_CARD = "vcard"  # NFC tag content: "vcard" (contact card + website) or "link" (website only)
RADAR_STATUS = "Ask me about MicroPython"  # Radar app; name + status limited to 25 bytes in total
REGION = "us"  # Options are us, cuba, eu, moldova, lebanon, egypt, chile, australia, nz
TIMEZONE = -7  # Offset from GMT as number of hours, i.e. 0, 1, -7 etc.
WATCH_REMOTE = True  # Badger Remote watch app (Bluetooth); False turns it off
