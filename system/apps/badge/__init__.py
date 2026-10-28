import os
import gc
import json
import math
import random
import time

import fetch
import machine
import missing_details
import wifi
from badgeware import link as badgelink

try:
    import secrets
except ImportError:
    secrets = None

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

phosphor = color.rgb(211, 250, 55, 150)
white = color.rgb(235, 245, 255)
faded = color.rgb(235, 245, 255, 100)
spinner = color.rgb(211, 250, 55, 50)
black = color.rgb(0, 0, 0)

mona_sans = missing_details.mona_sans()

HANDLE_SIZE = 28
NAME_SIZE = 16
VALUE_SIZE = 28
LABEL_SIZE = 14
NUDGE_SIZE = 17
NUDGE_RECT = (176, 70, 136, 150)

CONTRIB_URL = "https://github.com/{user}.contribs"
USER_AVATAR = "https://wsrv.nl/?url=https://github.com/{user}.png&w=150&output=png"
DETAILS_URL = "https://api.github.com/users/{user}"
EVENTS_URL = "https://api.github.com/users/{user}/events/public?per_page=10"

CACHE_DIR = "/state"
USER_FILE = f"{CACHE_DIR}/badge_user.json"
CONTRIB_FILE = f"{CACHE_DIR}/badge_contribs.json"
AVATAR_FILE = f"{CACHE_DIR}/badge_avatar.png"
EVENTS_FILE = f"{CACHE_DIR}/badge_events.json"

ACTIVITY_SIZE = 12
ACTIVITY_Y = 55
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# Up/down cycle through these after the stats page; images are 180px PNGs
QR_DIR = "/system/apps/badge"
QR_SIZE = 180
QR_TOP = 10
QR_PAGES = (
    ("qr_site.png", "christendijoux.com"),
    ("qr_linkedin.png", "linkedin.com/in/christen-dijoux"),
    ("qr_github.png", "github.com/Akiyo974"),
)

HEADERS = {"User-Agent": "GitHub Universe Badge 2026"}

RETRY_MS = 30000

fetch.AsyncFetch.MAX_HEADER_BYTES = 8192

GRAPH_WEEKS = 53
GRAPH_DAYS = 7
TILE_SIZE = 33
TILE_STEP = 37
GRAPH_TOP = (240 - GRAPH_DAYS * TILE_STEP) // 2
PARALLAX_SHIFT = 8
AVATAR_SIZE = 150
MATRIX_UPDATE_MS = 250
MATRIX_LEVELS = (0, 24, 55, 105, 175)
NFC_LINK = "https://christendijoux.com"

try:
    os.mkdir(CACHE_DIR)
except OSError:
    pass


class Tilt:
    GRAVITY = 16384.0
    SMOOTH_MS = 120
    RECENTRE_MS = 2800

    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.rest_z = None
        self.last_ticks = None

    def update(self):
        ax, _, az = badge.imu()[:3]
        now = badge.ticks
        dt = min(now - self.last_ticks, 200) if self.last_ticks is not None else 0
        self.last_ticks = now
        smooth = 1 - math.exp(-dt / self.SMOOTH_MS)
        recentre = 1 - math.exp(-dt / self.RECENTRE_MS)
        if self.rest_z is None:
            self.rest_z = az
        self.rest_z += (az - self.rest_z) * recentre
        target_x = max(-1.0, min(1.0, -ax / self.GRAVITY * 2))
        target_y = max(-1.0, min(1.0, (az - self.rest_z) / self.GRAVITY * 2))
        self.x += (target_x - self.x) * smooth
        self.y += (target_y - self.y) * smooth


tilt = Tilt()


def fake_number():
    return random.randint(10000, 99999)


def placeholder_if_none(text):
    if text:
        return text
    random.seed(badge.ticks // 100)
    chars = "!\"£$%^&*()_+-={}[]:@~;'#<>?,./\\|"
    return "".join(random.choice(chars) for _ in range(20))


class Download:
    def __init__(self, url, file, force_update):
        self.file = file
        self.temp_file = file + ".tmp"
        self.request = None
        if force_update or not file_exists(file):
            self.request = fetch.url(url, headers=HEADERS).to(self.temp_file)

    def ready(self):
        if self.request is None:
            return True
        if self.request:
            os.rename(self.temp_file, self.file)
            self.request = None
            return True
        return False

    @property
    def state(self):
        if self.request is None:
            return None
        return self.request.state

    @property
    def error(self):
        if self.request is None:
            return None
        return self.request.error


class ContributionMatrix:
    ADDRESS = 0x30
    ROW_MAP = (8, 5, 4, 3, 2, 1, 0, 7, 6)
    GLOBAL_CURRENT = 0x40

    def __init__(self):
        self.bus = None
        self.available = False
        self.frame = None
        self.last_update = 0
        self.original_pages = {}
        self.original_config = None
        self.original_current = None
        try:
            self.bus = machine.I2C()
            if self.ADDRESS not in self.bus.scan():
                return
            chip_id = self.bus.readfrom_mem(self.ADDRESS, 0xFC, 1)[0]
            if chip_id != 0x60:
                print("Badge matrix: unexpected device ID 0x%02x" % chip_id)
                return

            self.original_config = self.read_register(4, 0x00)
            self.original_current = self.read_register(4, 0x01)
            for page, count in ((0, 180), (1, 171), (2, 180), (3, 171)):
                self.original_pages[page] = self.read_page(page, count)

            self.write_page(2, bytes((0xFF,)) * 180)
            self.write_page(3, bytes((0xFF,)) * 171)
            self.write_page(0, bytes(180))
            self.write_page(1, bytes(171))
            self.write_register(4, 0x01, self.GLOBAL_CURRENT)
            self.write_register(4, 0x00, self.original_config | 0x01)
            self.frame = bytes(351)
            self.available = True
            print("Badge matrix: IS31FL3741 at 0x30, contribution graph ready")
        except (ImportError, OSError) as error:
            print("Badge matrix unavailable:", error)
            self.restore()

    def select_page(self, page):
        self.bus.writeto_mem(self.ADDRESS, 0xFE, b"\xC5")
        self.bus.writeto_mem(self.ADDRESS, 0xFD, bytes((page,)))

    def read_register(self, page, register):
        self.select_page(page)
        return self.bus.readfrom_mem(self.ADDRESS, register, 1)[0]

    def write_register(self, page, register, value):
        self.select_page(page)
        self.bus.writeto_mem(self.ADDRESS, register, bytes((value,)))

    def read_page(self, page, count):
        self.select_page(page)
        values = bytearray()
        for start in range(0, count, 30):
            length = min(30, count - start)
            values.extend(self.bus.readfrom_mem(self.ADDRESS, start, length))
        return bytes(values)

    def write_page(self, page, values):
        self.select_page(page)
        for start in range(0, len(values), 30):
            chunk = values[start:start + 30]
            self.bus.writeto(self.ADDRESS, bytes((start,)) + chunk)

    @classmethod
    def channel_addresses(cls, x, y):
        row = cls.ROW_MAP[y]
        led = x + row * 10 if x < 10 else x + 80 + row * 3
        offset = led * 3
        if x & 1 or x == 12:
            return offset + 2, offset, offset + 1
        return offset, offset + 1, offset + 2

    @classmethod
    def plot(cls, frame, x, y, red, green, blue):
        if 0 <= x < 13 and 0 <= y < 9:
            for address, value in zip(
                cls.channel_addresses(x, y), (red, green, blue)
            ):
                if value > frame[address]:
                    frame[address] = value

    def render(self, user, now):
        if not self.available or now - self.last_update < MATRIX_UPDATE_MS:
            return

        frame = bytearray(351)
        if user.contribution_data is None:
            if user.failed:
                self.plot(frame, 6, 0, 120, 0, 0)
            elif user.missing:
                self.plot(frame, 6, 0, 100, 45, 0)
            else:
                x = int(now / 250) % 13
                self.plot(frame, x, 0, 0, 80, 120)
        else:
            first_week = max(0, GRAPH_WEEKS - 13)
            for x in range(13):
                week = first_week + x
                weekly_total = 0
                for day in range(GRAPH_DAYS):
                    level = user.contribution_data[day][week]
                    weekly_total += level
                    self.plot(
                        frame, x, day + 1,
                        0, MATRIX_LEVELS[min(4, max(0, level))], 0,
                    )
                weekly_level = min(4, weekly_total // 7)
                self.plot(frame, x, 8, 0, MATRIX_LEVELS[weekly_level], 0)
            self.plot(frame, 6, 0, 0, 0, 100)

        if frame != self.frame:
            self.write_page(0, frame[:180])
            self.write_page(1, frame[180:])
            self.frame = bytes(frame)
        self.last_update = now

    def restore(self):
        if self.bus is None or self.original_config is None:
            return
        try:
            for page in (0, 1, 2, 3):
                if page in self.original_pages:
                    self.write_page(page, self.original_pages[page])
            if self.original_current is not None:
                self.write_register(4, 0x01, self.original_current)
            self.write_register(4, 0x00, self.original_config)
        except OSError as error:
            print("Badge matrix restore failed:", error)
        self.available = False


class NFCLink:
    ADDRESS = 0x53
    WRITE_BLOCK_SIZE = 4
    WRITE_CYCLE_MS = 6

    def __init__(self, bus=None):
        self.bus = bus
        self.pending = None
        self.offset = 0
        self.cursor = 0
        self.next_write = 0
        self.state = "unavailable"
        try:
            if self.bus is None:
                self.bus = machine.I2C()
            if self.ADDRESS not in self.bus.scan():
                print("Badge NFC: ST25DV user memory not found")
                return

            cc = self.bus.readfrom_mem(self.ADDRESS, 0, 8, addrsize=16)
            if cc[0] not in (0xE1, 0xE2) or cc[1] & 0xFC != 0x40:
                print("Badge NFC: tag has no valid Type 5 capability container")
                return

            self.offset = 8 if cc[2] == 0 else 4
            header = self.bus.readfrom_mem(
                self.ADDRESS, self.offset, 4, addrsize=16
            )
            if header[0] != 0x03:
                print("Badge NFC: tag has no NDEF message TLV")
                return

            ndef_length = header[1]
            if ndef_length == 0xFF:
                ndef_length = (header[2] << 8) | header[3]
                message_offset = self.offset + 4
            else:
                message_offset = self.offset + 2

            payload = b"\x04" + NFC_LINK[8:].encode()
            record = b"\xd1\x01" + bytes((len(payload),)) + b"U" + payload
            self.pending = bytes((0x03, len(record))) + record + b"\xfe"
            if ndef_length == len(record):
                current = self.bus.readfrom_mem(
                    self.ADDRESS, message_offset, ndef_length, addrsize=16
                )
                if current == record:
                    self.pending = None
                    self.state = "ready"
                    print("Badge NFC: site link already programmed")
                    return

            if len(self.pending) > 0xFF:
                print("Badge NFC: site link is too large for a short NDEF record")
                self.pending = None
                return

            self.state = "writing"
            print("Badge NFC: programming site link")
        except (ImportError, OSError, TypeError) as error:
            print("Badge NFC unavailable:", error)
            self.pending = None

    def update(self, now):
        if self.state != "writing" or self.pending is None or now < self.next_write:
            return

        if self.cursor < len(self.pending):
            end = min(self.cursor + self.WRITE_BLOCK_SIZE, len(self.pending))
            chunk = self.pending[self.cursor:end]
            try:
                self.bus.writeto_mem(
                    self.ADDRESS,
                    self.offset + self.cursor,
                    chunk,
                    addrsize=16,
                )
            except (OSError, TypeError) as error:
                self.state = "failed"
                print("Badge NFC write failed:", error)
                return
            self.cursor = end
            self.next_write = now + self.WRITE_CYCLE_MS
            return

        try:
            written = self.bus.readfrom_mem(
                self.ADDRESS, self.offset, len(self.pending), addrsize=16
            )
        except (OSError, TypeError) as error:
            self.state = "failed"
            print("Badge NFC verification failed:", error)
            return

        if written != self.pending:
            self.state = "failed"
            print("Badge NFC verification failed: readback mismatch")
            return

        self.state = "ready"
        print("Badge NFC: site link programmed")


class User:
    levels = [
        color.rgb(10, 13, 17),
        color.rgb(1, 29, 11),
        color.rgb(12, 54, 23),
        color.rgb(23, 80, 33),
        color.rgb(43, 105, 50),
    ]

    def __init__(self, handle):
        self.handle = handle
        self.tile = shape.rounded_rectangle(0, 0, TILE_SIZE, TILE_SIZE, 4)
        self.update()

    def update(self, force_update=False):
        self.name = None
        self.followers = None
        self.contribs = None
        self.contribution_data = None
        self.repos = None
        self.avatar = None
        self._download = None
        self._force_update = force_update
        self._error = None
        self._retry_at = 0
        self.missing = []

    def load_user_data(self):
        with open(USER_FILE, "r") as f:
            data = json.load(f)
        if data["login"].lower() != self.handle.lower():
            self.update(True)
            return
        self.name = data["name"] or data["login"]
        self.handle = data["login"]
        self.followers = data["followers"]
        self.repos = data["public_repos"]
        del data
        gc.collect()

    def load_contrib_data(self):
        with open(CONTRIB_FILE, "r") as f:
            data = json.load(f)
        self.contribs = data["total_contributions"]
        self.contribution_data = [[0 for _ in range(GRAPH_WEEKS)] for _ in range(GRAPH_DAYS)]
        for week_index, week in enumerate(data["weeks"][:GRAPH_WEEKS]):
            for day, contribution in enumerate(week["contribution_days"][:GRAPH_DAYS]):
                self.contribution_data[day][week_index] = contribution["level"]
        del data
        gc.collect()

    def load_avatar(self):
        self.avatar = image.load(AVATAR_FILE)

    def next_download(self):
        if self.name is None:
            return "fetching user data...", DETAILS_URL, USER_FILE, self.load_user_data
        if self.contribs is None:
            return "fetching contribs...", CONTRIB_URL, CONTRIB_FILE, self.load_contrib_data
        if self.avatar is None:
            return "fetching avatar...", USER_AVATAR, AVATAR_FILE, self.load_avatar
        return None

    def fail(self, error):
        print(f"Badge: {error}")
        self._error = error
        self._retry_at = badge.ticks + RETRY_MS
        self._download = None

    def fetch_step(self):
        if self._error:
            if badge.ticks < self._retry_at:
                return "fetch failed, retrying..."
            self._error = None

        pending = self.next_download()
        if pending is None:
            return None

        label, url, file, load = pending

        if self._download is None or self._download.file != file:
            if self._force_update or not file_exists(file):
                self.missing = missing_details.missing("WIFI_SSID")
                if self.missing:
                    return label
            self._download = Download(url.format(user=self.handle), file, self._force_update)

        if self._download.ready():
            self._download = None
            try:
                load()
            except (OSError, ValueError, KeyError) as e:
                os.remove(file)
                self.fail(e)
            return label

        if self._download.error:
            self.fail(self._download.error)
            return label

        return self._download.state if self._download.state not in ("Idle", "Fetching") else label

    @property
    def loaded(self):
        return self.name is not None

    @property
    def failed(self):
        return self._error is not None

    def draw_stat(self, title, value, x, y):
        screen.font = mona_sans
        screen.pen = white if value else faded
        if value is not None:
            text = str(value)
        elif self.failed:
            text = "-"
        else:
            text = str(fake_number())
        screen.text(text, x, y, VALUE_SIZE)
        screen.pen = phosphor
        screen.text(title, x, y + VALUE_SIZE + 2, LABEL_SIZE)

    def draw_graph(self):
        graph_width = GRAPH_WEEKS * TILE_STEP
        travel = (graph_width - screen.width) / 2
        offset_x = int(-math.sin(badge.ticks / 5000) * travel + travel + tilt.x * PARALLAX_SHIFT)
        offset_y = GRAPH_TOP - int(tilt.y * PARALLAX_SHIFT)

        for y in range(GRAPH_DAYS):
            for x in range(GRAPH_WEEKS):
                pos_x = x * TILE_STEP - offset_x
                if pos_x + TILE_SIZE < 0 or pos_x > screen.width:
                    continue
                level = self.contribution_data[y][x] if self.contribution_data else 1
                screen.pen = User.levels[level]
                self.tile.transform = mat3().translate(pos_x, y * TILE_STEP + offset_y)
                screen.shape(self.tile)

    def draw_avatar(self):
        if self.avatar:
            screen.blit(self.avatar, rect(10, 74, AVATAR_SIZE, AVATAR_SIZE))
            return

        squircle = shape.squircle(0, 0, 20, 5)
        screen.pen = spinner
        for i in range(4):
            mul = math.sin(badge.ticks / 1000) * 14000
            squircle.transform = mat3().translate(85, 149).rotate((badge.ticks + i * mul) / 40).scale(1 + i / 1.3)
            screen.shape(squircle)

    def draw(self, status):
        self.draw_graph()

        screen.font = mona_sans
        screen.pen = white
        center_text(status or self.handle, 4, HANDLE_SIZE)

        screen.pen = phosphor
        center_text(placeholder_if_none(self.name), 36, NAME_SIZE)

        line = activity.line()
        if line:
            screen.pen = faded
            center_text(line, ACTIVITY_Y, ACTIVITY_SIZE)

        self.draw_stat("followers", self.followers, 176, 66)
        self.draw_stat("contribs", self.contribs, 176, 124)
        self.draw_stat("repos", self.repos, 176, 182)

        self.draw_avatar()


class Activity:
    """Latest public push, refreshed once per launch, cached for offline use."""

    def __init__(self, handle):
        self.handle = handle
        self.label = None
        self.repo = None
        self.created = None
        self._request = None
        self._done = not handle
        self._clock_offset = None
        self.load()

    def load(self):
        try:
            with open(EVENTS_FILE, "r") as f:
                events = json.load(f)
        except (OSError, ValueError):
            return
        # Forget what was shown before: the new list may be empty or for another user
        self.label = self.repo = self.created = None
        handle = self.handle.lower()
        fallback = None
        for event in events if isinstance(events, list) else []:
            if str(event.get("actor", {}).get("login", "")).lower() != handle:
                continue
            if event.get("type") == "PushEvent":
                fallback = event
                break
            if fallback is None:
                fallback = event
        if fallback is not None:
            self.label = "Last push" if fallback["type"] == "PushEvent" else "Last activity"
            self.repo = fallback["repo"]["name"].split("/")[-1]
            self.created = fallback["created_at"]
        del events
        gc.collect()

    def step(self):
        if self._done:
            return
        if self._request is None:
            if missing_details.missing("WIFI_SSID"):
                self._done = True
                return
            self._request = fetch.url(EVENTS_URL.format(user=self.handle), headers=HEADERS).to(EVENTS_FILE + ".tmp")
        if self._request:
            self._done = True
            try:
                os.remove(EVENTS_FILE)
            except OSError:
                pass
            os.rename(EVENTS_FILE + ".tmp", EVENTS_FILE)
            self.load()
            self.sync_clock()
        elif self._request.error:
            print(f"Badge: activity {self._request.error}")
            self._done = True

    def sync_clock(self):
        # Only measure the offset from NTP; the RTC itself is left alone
        try:
            import ntptime
            self._clock_offset = ntptime.time() - time.time()
        except Exception as e:  # noqa: BLE001
            print(f"Badge: ntp {e}")

    def age(self):
        if self.created is None or self._clock_offset is None:
            return None
        c = self.created
        then = time.mktime((int(c[0:4]), int(c[5:7]), int(c[8:10]), int(c[11:13]), int(c[14:16]), int(c[17:19]), 0, 0))
        seconds = time.time() + self._clock_offset - then
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"
        return f"{seconds // 86400}d ago"

    def line(self):
        if self.repo is None:
            return None
        when = self.age()
        if when is None:
            c = self.created
            when = f"{MONTHS[int(c[5:7]) - 1]} {int(c[8:10])}"
        return f"{self.label}: {self.repo} - {when}"


class QRPages:
    def __init__(self):
        self.page = 0
        self.images = [None] * len(QR_PAGES)

    def handle_buttons(self):
        count = len(QR_PAGES) + 1
        if badge.pressed(BUTTON_DOWN):
            self.page = (self.page + 1) % count
        if badge.pressed(BUTTON_UP):
            self.page = (self.page - 1) % count

    @property
    def showing(self):
        return self.page > 0

    def draw(self):
        index = self.page - 1
        file, caption = QR_PAGES[index]
        if self.images[index] is None:
            self.images[index] = image.load(f"{QR_DIR}/{file}")

        user.draw_graph()
        screen.pen = color.rgb(0, 0, 0, 170)
        screen.rectangle(0, 0, screen.width, screen.height)

        left = (screen.width - QR_SIZE) // 2
        screen.pen = white
        screen.shape(shape.rounded_rectangle(left - 6, QR_TOP - 6, QR_SIZE + 12, QR_SIZE + 12, 8))
        screen.blit(self.images[index], rect(left, QR_TOP, QR_SIZE, QR_SIZE))

        screen.font = mona_sans
        screen.pen = phosphor
        center_text(caption, QR_TOP + QR_SIZE + 12, NAME_SIZE)
        screen.pen = faded
        center_text(f"{self.page} / {len(QR_PAGES)}", QR_TOP + QR_SIZE + 32, LABEL_SIZE)


def center_text(text, y, size):
    w, _ = screen.measure_text(text, font_size=size)
    if w > screen.width - 16:
        size = size * (screen.width - 16) / w
        w = screen.width - 16
    screen.text(text, screen.width / 2 - w / 2, y, size)


def setting(key):
    return str(getattr(secrets, key, "") or "").strip()


def linkedin_label(url):
    if not url:
        return ""
    path = url.split("://")[-1]
    if path.startswith("www."):
        path = path[4:]
    return path.rstrip("/")


handle = setting("GITHUB_USERNAME")
contact_name = setting("CONTACT_NAME")
linkedin = linkedin_label(setting("CONTACT_LINKEDIN"))
user = User(handle)
activity = Activity(handle)
qr_pages = QRPages()
badge_id = bytes(machine.unique_id())[:badgelink.ID_LEN]
matrix = ContributionMatrix()
nfc_link = NFCLink(matrix.bus)


def draw_simple(status):
    user.draw_graph()
    screen.font = mona_sans
    screen.pen = white
    center_text(contact_name or handle or linkedin, 4, HANDLE_SIZE)
    details = []
    if handle and contact_name:
        details.append("@" + handle)
    if linkedin and (contact_name or handle):
        details.append(linkedin)
    screen.pen = phosphor
    for index, line in enumerate(details):
        center_text(line, 36 + index * 18, NAME_SIZE)
    badgelink.draw_identicon(screen, badge_id, 10, 74, AVATAR_SIZE)

    if not handle:
        nudge = "Add your GitHub username in Settings or visit Hack Your Badge to show your stats"
    elif user.failed and wifi.failure():
        nudge = "Couldn't connect to WiFi. Visit the Hack Your Badge station to get your GitHub stats"
    elif user.missing or user.failed:
        nudge = "Visit the Hack Your Badge station to get your GitHub stats"
    else:
        nudge = status or "connecting to GitHub..."
    screen.pen = white
    screen.text(nudge, rect(*NUDGE_RECT), NUDGE_SIZE, align=(LEFT, TOP))


def update():
    tilt.update()

    screen.pen = black
    screen.clear()

    matrix.render(user, badge.ticks)
    nfc_link.update(badge.ticks)

    if not handle and not contact_name and not linkedin:
        missing_details.show([], user.draw_graph, ("your name, GitHub username,", "and LinkedIn stub"))
        return

    both_held = badge.held(BUTTON_LEFT) and badge.held(BUTTON_RIGHT)
    if handle and both_held and (badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT)):
        user.update(True)

    status = user.fetch_step() if handle else None
    if user.next_download() is None:
        activity.step()

    qr_pages.handle_buttons()
    if qr_pages.showing:
        qr_pages.draw()
        return

    if user.loaded:
        user.draw(status)
    else:
        draw_simple(status)


def on_exit():
    matrix.restore()


run(update)
