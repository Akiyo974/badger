"""
Radar: the badges around you, placed by how close they are.

Bluetooth gives a signal strength, not a direction, so a badge's distance from
the centre is real but its angle is only a stable spot picked from its id.

Unmodified badges show up while they run Contacts, Pong or Merge Conflict
(their link layer advertises then). Badges running Radar are always visible
and also share a short status, set with RADAR_STATUS in secrets.py.

Controls:
* Select = Switch between the radar and the list
* Up / Down = Scroll the list
"""
import math
import struct

import bluetooth
import missing_details
from badgeware import link as badgelink

try:
    import secrets
except ImportError:
    secrets = None

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

# Advertising formats. Stock badges: manufacturer data ffff "BL" version, game
# code, 8-byte id; their scan response carries 00ff "N" + name. Radar badges:
# ffff "RD" version, 8-byte id; scan response ffff "RS" + "name|status".
COMPANY = b"\xff\xff"
STOCK_MAGIC = COMPANY + b"BL"
STOCK_NAME = b"\x00\xffN"
RADAR_MAGIC = COMPANY + b"RD"
RADAR_TEXT = COMPANY + b"RS"
RADAR_VERSION = 1
TEXT_LIMIT = 25

IRQ_SCAN_RESULT = 5
ADV_SCAN_RSP = 4
SCAN_INTERVAL_US = 60000
SCAN_WINDOW_US = 40000
ADV_INTERVAL_US = 200000

FORGET_MS = 12000
RSSI_SMOOTH = 0.25
QUEUE_LIMIT = 64

# Rough distance from signal strength: -59 dBm at 1 m, indoor fall-off
RSSI_AT_1M = -59
PATH_LOSS = 2.5
CLOSEST_RSSI = -45
FARTHEST_RSSI = -95

GAMES = ("contacts", "pong", "merge conflict")

WIDTH = 320
HEIGHT = 240
CX = 118
CY = 120
RADIUS = 108
SWEEP_MS = 3000
DOT_SIZE = 22
PANEL_X = 244
ROW_HEIGHT = 46
VISIBLE_ROWS = 4

black = color.rgb(0, 0, 0)
white = color.rgb(255, 255, 255)
dim = color.rgb(255, 255, 255, 140)
faint = color.rgb(255, 255, 255, 50)
grid = color.rgb(95, 237, 131, 70)
sweep = color.rgb(95, 237, 131, 40)
accent = color.rgb(95, 237, 131)
row_fill = color.rgb(30, 34, 40)

body_font = missing_details.mona_sans()


def secret(key):
    return str(getattr(secrets, key, "") or "").strip()


def utf8_cut(text, limit):
    data = text.encode()
    while len(data) > limit:
        text = text[:-1]
        data = text.encode()
    return data


def game_codes():
    codes = {}
    for game in GAMES:
        try:
            code = badgelink.game_code(game)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(code, int):
            code = struct.pack("<H", code & 0xFFFF)
        codes[bytes(code)[:2]] = game
    return codes


def fields(data):
    index = 0
    while index + 1 < len(data):
        length = data[index]
        if length == 0 or index + 1 + length > len(data):
            return
        yield data[index + 1], data[index + 2:index + 1 + length]
        index += 1 + length


def distance_m(rssi):
    return 10 ** ((RSSI_AT_1M - rssi) / (10 * PATH_LOSS))


def distance_label(rssi):
    metres = distance_m(rssi)
    if metres < 1:
        return "right here"
    if metres < 10:
        return f"~{metres:.0f} m"
    return "far away"


class Peer:
    def __init__(self, badge_id, now):
        self.id = badge_id
        self.name = ""
        self.status = ""
        self.game = ""
        self.radar = False
        self.rssi = None
        self.seen = now
        # Stable pseudo-angle from the id: Bluetooth gives no direction
        self.angle = (badge_id[0] << 8 | badge_id[1]) / 65536 * 2 * math.pi

    def heard(self, rssi, now):
        self.rssi = rssi if self.rssi is None else self.rssi + (rssi - self.rssi) * RSSI_SMOOTH
        self.seen = now

    @property
    def label(self):
        return self.name or badgelink.badge_name(self.id)

    @property
    def closeness(self):
        span = CLOSEST_RSSI - FARTHEST_RSSI
        return max(0.0, min(1.0, (self.rssi - FARTHEST_RSSI) / span))


class Radar:
    def __init__(self):
        self.my_id = bytes(machine_id())[:badgelink.ID_LEN]
        self.my_name = secret("CONTACT_NAME") or badgelink.badge_name(self.my_id)
        self.my_status = secret("RADAR_STATUS")
        self.codes = game_codes()
        self.peers = {}
        self.addresses = {}
        self.queue = []
        self.list_view = False
        self.top_row = 0
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self.irq)
        self.advertise()
        self.ble.gap_scan(0, SCAN_INTERVAL_US, SCAN_WINDOW_US, True)

    def advertise(self):
        flags = b"\x02\x01\x06"
        body = RADAR_MAGIC + bytes((RADAR_VERSION,)) + self.my_id
        adv = flags + bytes((len(body) + 1, 0xFF)) + body
        text = utf8_cut(self.my_name, 12) + b"|" + self.my_status.encode()
        text = utf8_cut(text.decode(), TEXT_LIMIT)
        rsp_body = RADAR_TEXT + text
        rsp = bytes((len(rsp_body) + 1, 0xFF)) + rsp_body
        self.ble.gap_advertise(ADV_INTERVAL_US, adv_data=adv, resp_data=rsp)

    def irq(self, event, data):
        # Keep the interrupt short: copy and queue, parse in update()
        if event == IRQ_SCAN_RESULT and len(self.queue) < QUEUE_LIMIT:
            _, addr, adv_type, rssi, adv = data
            self.queue.append((bytes(addr), adv_type, rssi, bytes(adv)))

    def close(self):
        try:
            self.ble.gap_scan(None)
            self.ble.gap_advertise(None)
        except OSError:
            pass
        badge.caselights(0)

    def handle(self, addr, adv_type, rssi, adv, now):
        badge_id = None
        game = None
        radar = False
        name = None
        status = None
        for kind, value in fields(adv):
            if kind != 0xFF:
                continue
            if value[:4] == STOCK_MAGIC and len(value) >= 15:
                game = self.codes.get(bytes(value[5:7]), "")
                badge_id = bytes(value[7:15])
            elif value[:4] == RADAR_MAGIC and len(value) >= 13:
                radar = True
                badge_id = bytes(value[5:13])
            elif value[:3] == STOCK_NAME:
                name = value[3:].decode("utf-8", "ignore")
            elif value[:4] == RADAR_TEXT:
                parts = value[4:].decode("utf-8", "ignore").split("|", 1)
                name = parts[0]
                status = parts[1] if len(parts) > 1 else ""

        if badge_id is None:
            # A scan response only carries text: match it by address
            badge_id = self.addresses.get(addr)
            if badge_id is None or adv_type != ADV_SCAN_RSP:
                return
        if badge_id == self.my_id:
            return

        self.addresses[addr] = badge_id
        peer = self.peers.get(badge_id)
        if peer is None:
            peer = self.peers[badge_id] = Peer(badge_id, now)
        if adv_type != ADV_SCAN_RSP:
            peer.heard(rssi, now)
        # An identity advert says which app the badge runs now: drop what the
        # other format left behind (a text-only scan response changes nothing)
        if radar:
            peer.radar = True
            peer.game = ""
        if game is not None:
            peer.radar = False
            peer.status = ""
            peer.game = game
        if name:
            peer.name = name
        if status is not None:
            peer.status = status

    def nearby(self):
        return sorted((peer for peer in self.peers.values() if peer.rssi is not None), key=lambda peer: -peer.rssi)

    def update(self, now):
        while self.queue:
            self.handle(*self.queue.pop(0), now)
        gone = {key for key, peer in self.peers.items() if now - peer.seen > FORGET_MS}
        if gone:
            for badge_id in gone:
                del self.peers[badge_id]
            self.addresses = {addr: badge_id for addr, badge_id in self.addresses.items() if badge_id not in gone}

        peers = self.nearby()
        last_top = max(0, len(peers) - VISIBLE_ROWS)
        if badge.pressed(BUTTON_SELECT):
            self.list_view = not self.list_view
            self.top_row = 0
        if self.list_view and peers:
            if badge.pressed(BUTTON_DOWN):
                self.top_row += 1
            if badge.pressed(BUTTON_UP):
                self.top_row -= 1
        # Badges leave the list on their own, so clamp every frame
        self.top_row = max(0, min(self.top_row, last_top))

        # Case lights glow brighter as the closest badge gets nearer
        if peers:
            pulse = 0.75 + 0.25 * math.sin(now / 250)
            badge.caselights(peers[0].closeness * pulse)
        else:
            badge.caselights(0)
        return peers

    def draw(self, peers, now):
        screen.pen = black
        screen.clear()
        if self.list_view:
            self.draw_list(peers)
        else:
            self.draw_radar(peers, now)
            self.draw_panel(peers)

    def draw_radar(self, peers, now):
        screen.pen = grid
        for ring in (1, 2, 3):
            r = RADIUS * ring / 3
            screen.shape(shape.circle(CX, CY, r).stroke(1))
        centre = vec2(CX, CY)
        screen.line(vec2(CX - RADIUS, CY), vec2(CX + RADIUS, CY))
        screen.line(vec2(CX, CY - RADIUS), vec2(CX, CY + RADIUS))

        # Rotating sweep, purely decorative
        angle = (now % SWEEP_MS) / SWEEP_MS * 2 * math.pi
        screen.pen = sweep
        for step in range(8):
            a = angle - step * 0.06
            screen.line(centre, vec2(CX + math.cos(a) * RADIUS, CY + math.sin(a) * RADIUS))
        screen.pen = accent
        screen.line(centre, vec2(CX + math.cos(angle) * RADIUS, CY + math.sin(angle) * RADIUS))

        for peer in reversed(peers):
            r = (1 - peer.closeness) * (RADIUS - DOT_SIZE / 2)
            x = CX + math.cos(peer.angle) * r - DOT_SIZE / 2
            y = CY + math.sin(peer.angle) * r - DOT_SIZE / 2
            badgelink.draw_identicon(screen, peer.id, int(x), int(y), DOT_SIZE)

        badgelink.draw_identicon(screen, self.my_id, CX - 8, CY - 8, 16)

    def draw_panel(self, peers):
        screen.font = body_font
        screen.pen = white
        screen.text(str(len(peers)), PANEL_X, 6, 40)
        screen.pen = dim
        screen.text("badge" if len(peers) == 1 else "badges", PANEL_X, 50, 14)
        screen.text("nearby", PANEL_X, 66, 14)
        if peers:
            nearest = peers[0]
            screen.pen = accent
            screen.text("closest", PANEL_X, 104, 12)
            screen.pen = white
            screen.text(fit(nearest.label, 72, 14), PANEL_X, 120, 14)
            screen.pen = dim
            screen.text(distance_label(nearest.rssi), PANEL_X, 138, 13)
        else:
            screen.pen = dim
            screen.text("scanning", PANEL_X, 104, 13)
        screen.pen = faint
        screen.text("select: list", PANEL_X, 218, 12)

    def draw_list(self, peers):
        screen.font = body_font
        if not peers:
            screen.pen = white
            centred("no badges nearby yet", 96, 18)
            screen.pen = dim
            centred("they show up while running", 124, 14)
            centred("Radar, Contacts, Pong or Merge Conflict", 142, 14)
            return
        for slot, peer in enumerate(peers[self.top_row:self.top_row + VISIBLE_ROWS]):
            top = 6 + slot * (ROW_HEIGHT + 4)
            screen.pen = row_fill
            screen.rectangle(4, top, WIDTH - 8, ROW_HEIGHT)
            badgelink.draw_identicon(screen, peer.id, 10, top + 6, ROW_HEIGHT - 12)
            screen.pen = white
            screen.text(fit(peer.label, 170, 16), 54, top + 5, 16)
            screen.pen = dim
            detail = peer.status or ("in " + peer.game if peer.game else ("Radar" if peer.radar else ""))
            screen.text(fit(detail, 170, 13), 54, top + 25, 13)
            screen.pen = accent
            text = distance_label(peer.rssi)
            w, _ = screen.measure_text(text, font_size=13)
            screen.text(text, WIDTH - 12 - w, top + 16, 13)
        screen.pen = faint
        centred("select: radar   up/down: scroll", 222, 12)


def machine_id():
    import machine
    return machine.unique_id()


def fit(text, width, size):
    while text and screen.measure_text(text, font_size=size)[0] > width:
        text = text[:-1]
    return text


def centred(text, y, size):
    w, _ = screen.measure_text(text, font_size=size)
    screen.text(text, (WIDTH - w) / 2, y, size)


radar = Radar()


def update():
    now = badge.ticks
    peers = radar.update(now)
    radar.draw(peers, now)


def on_exit():
    radar.close()


run(update)
