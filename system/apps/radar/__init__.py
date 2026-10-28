"""
Radar: nearby badges, with signal-based proximity, not measured distance.

Bluetooth gives no direction: each angle is a stable spot picked from the id.

Unmodified badges show up while they run Contacts, Pong or Merge Conflict
(their link layer advertises then). Badges running Radar are always visible
and also share a short status, set with RADAR_STATUS in secrets.py.

Controls:
* Select = Switch between the radar and the list
* Up / Down = Choose a badge in the list
* Right = History on the radar, or start Hot / Cold from the list
* In the game: Select = Found!, Left = Quit
"""
import math
import struct

import bluetooth
import missing_details
from badgeware import State
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

IRQ_CENTRAL_CONNECT = 1
IRQ_CENTRAL_DISCONNECT = 2
IRQ_SCAN_RESULT = 5
IRQ_SCAN_DONE = 6
ADV_SCAN_RSP = 4
SCAN_INTERVAL_US = 60000
SCAN_WINDOW_US = 40000
ADV_INTERVAL_US = 200000

FORGET_MS = 12000
FADE_AFTER_MS = 4000
RSSI_SMOOTH_MS = 800
QUEUE_LIMIT = 64
HISTORY_LIMIT = 200
HISTORY_STATE = "radar_history"
HISTORY_SAVE_MS = 10000

CLOSEST_RSSI = -45
FARTHEST_RSSI = -95
VERY_NEAR_RSSI = -60
NEAR_RSSI = -75
RSSI_HYSTERESIS = 3
PROXIMITY_LABELS = ("Far", "Near", "Very near")

GAMES = ("contacts", "pong", "merge conflict")

WIDTH = 320
HEIGHT = 240
CX = 118
CY = 112
RADIUS = 98
SWEEP_MS = 3000
DOT_SIZE = 22
MIN_PEER_RADIUS = 24
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


def packet_kind(adv_type, data):
    for kind, value in fields(data):
        if kind != 0xFF:
            continue
        if adv_type == ADV_SCAN_RSP:
            if value[:3] == STOCK_NAME or value[:4] == RADAR_TEXT:
                return 2
        elif (
            (value[:4] == STOCK_MAGIC and len(value) >= 15)
            or (value[:4] == RADAR_MAGIC and len(value) >= 13 and value[4] == RADAR_VERSION)
        ):
            return 1
    return 0


def signal_radius(closeness):
    return MIN_PEER_RADIUS + (1 - closeness) * (RADIUS - DOT_SIZE / 2 - MIN_PEER_RADIUS)


def signal_closeness(rssi):
    return max(0.0, min(1.0, (rssi - FARTHEST_RSSI) / (CLOSEST_RSSI - FARTHEST_RSSI)))


class MatrixDisplay:
    ADDRESS = 0x30
    WIDTH = 13
    HEIGHT = 9
    ROW_MAP = (8, 5, 4, 3, 2, 1, 0, 7, 6)
    REFRESH_MS = 120
    GLOBAL_CURRENT = 0x40

    def __init__(self):
        self.bus = None
        self.available = False
        self.last_frame = None
        self.last_update = 0
        self.original_pages = {}
        self.original_config = None
        self.original_current = None
        try:
            from machine import I2C

            self.bus = I2C()
            if self.ADDRESS not in self.bus.scan():
                return
            chip_id = self.bus.readfrom_mem(self.ADDRESS, 0xFC, 1)[0]
            if chip_id != 0x60:
                print("Radar matrix: unexpected device ID 0x%02x" % chip_id)
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
            self.last_frame = bytes(351)
            self.available = True
            print("Radar matrix: IS31FL3741 at 0x30, 13x9 RGB")
        except (ImportError, OSError) as error:
            print("Radar matrix unavailable:", error)
            # Undo whatever part of the setup went through
            self.close()

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
        if 0 <= x < cls.WIDTH and 0 <= y < cls.HEIGHT:
            for address, value in zip(
                cls.channel_addresses(x, y), (red, green, blue)
            ):
                if value > frame[address]:
                    frame[address] = value

    def render(self, peers, now):
        if not self.available or now - self.last_update < self.REFRESH_MS:
            return
        frame = bytearray(351)
        for radius in (1, 2, 3, 4):
            for x, y in (
                (6 + radius, 4), (6 - radius, 4),
                (6, 4 + radius), (6, 4 - radius),
            ):
                self.plot(frame, x, y, 0, 18, 0)

        angle = (now % SWEEP_MS) / SWEEP_MS * 2 * math.pi
        for step in range(1, 5):
            x = 6 + round(math.cos(angle) * step * 1.4)
            y = 4 + round(math.sin(angle) * step)
            level = 100 - step * 12
            self.plot(frame, x, y, 0, level, 0)
        self.plot(frame, 6, 4, 0, 0, 120)

        for peer in peers:
            radius = max(1, round((1 - peer.closeness) * 4))
            x = 6 + round(math.cos(peer.angle) * radius * 1.4)
            y = 4 + round(math.sin(peer.angle) * radius)
            level = int((80 + peer.closeness * 175) * peer.visibility(now))
            if peer.radar:
                red, green, blue = 0, level // 2, level
            elif peer.game == "pong":
                red, green, blue = level, level // 3, 0
            elif peer.game == "contacts":
                red, green, blue = level, level, 0
            elif peer.game:
                red, green, blue = level, 0, level // 2
            else:
                red, green, blue = 0, level, level // 4
            self.plot(frame, x, y, red, green, blue)

        if frame != self.last_frame:
            try:
                self.write_page(0, frame[:180])
                self.write_page(1, frame[180:])
            except OSError as error:
                # The matrix is optional: drop it, keep scanning
                print("Radar matrix write failed:", error)
                self.close()
                return
            self.last_frame = bytes(frame)
        self.last_update = now

    def close(self):
        # Best effort: restores whatever was saved, even after a partial setup
        if self.bus is None or self.original_config is None:
            self.available = False
            return
        try:
            for page in (0, 1, 2, 3):
                if page in self.original_pages:
                    self.write_page(page, self.original_pages[page])
            if self.original_current is not None:
                self.write_register(4, 0x01, self.original_current)
            self.write_register(4, 0x00, self.original_config)
        except OSError as error:
            print("Radar matrix restore failed:", error)
        self.available = False


class HapticFeedback:
    ADDRESS = 0x5A
    # Device id in STATUS bits 7:5: 0x60 for the DRV2605, 0xE0 for the DRV2605L
    DEVICE_IDS = (0x60, 0xE0)
    LIBRARY_ERM = 0x01
    EFFECT_STRONG_CLICK_60 = 0x02
    MIN_INTERVAL_MS = 350

    def __init__(self):
        self.bus = None
        self.available = False
        self.pending = False
        self.last_played = None
        try:
            from machine import I2C

            self.bus = I2C()
            if self.ADDRESS not in self.bus.scan():
                return
            status = self.bus.readfrom_mem(self.ADDRESS, 0x00, 1)[0]
            if status & 0xE0 not in self.DEVICE_IDS:
                print("Radar haptics: unexpected DRV2605 ID 0x%02x" % status)
                return
            self.bus.writeto_mem(self.ADDRESS, 0x01, b"\x00")
            self.bus.writeto_mem(self.ADDRESS, 0x03, bytes((self.LIBRARY_ERM,)))
            for register in range(0x04, 0x0C):
                self.bus.writeto_mem(self.ADDRESS, register, b"\x00")
            self.available = True
            print("Radar haptics: DRV2605 ERM at 0x5a")
        except (ImportError, OSError) as error:
            print("Radar haptics unavailable:", error)

    def queue(self):
        if self.available:
            self.pending = True

    def update(self, now):
        if not self.available or not self.pending:
            return
        if self.last_played is not None and now - self.last_played < self.MIN_INTERVAL_MS:
            return
        try:
            self.bus.writeto_mem(
                self.ADDRESS, 0x04, bytes((self.EFFECT_STRONG_CLICK_60,))
            )
            self.bus.writeto_mem(self.ADDRESS, 0x05, b"\x00")
            self.bus.writeto_mem(self.ADDRESS, 0x0C, b"\x01")
            self.pending = False
            self.last_played = now
        except OSError as error:
            print("Radar haptics failed:", error)
            self.available = False
            self.pending = False


class Peer:
    def __init__(self, badge_id, now):
        self.id = badge_id
        self.name = ""
        self.status = ""
        self.game = ""
        self.radar = False
        self.rssi = None
        self.samples = []
        self.zone = 0
        self.seen = now
        self.address = None
        # Stable pseudo-angle from the id: Bluetooth gives no direction
        self.angle = (badge_id[0] << 8 | badge_id[1]) / 65536 * 2 * math.pi

    def heard(self, rssi, now):
        if now < self.seen:
            return
        elapsed = now - self.seen
        if self.rssi is None or elapsed >= FADE_AFTER_MS:
            self.samples = [rssi]
            self.rssi = rssi
            self.zone = 2 if rssi >= VERY_NEAR_RSSI else (1 if rssi >= NEAR_RSSI else 0)
        else:
            self.samples.append(rssi)
            del self.samples[:-3]
            median = sorted(self.samples)[len(self.samples) // 2]
            amount = 1 - math.exp(-elapsed / RSSI_SMOOTH_MS)
            self.rssi += (median - self.rssi) * amount
            thresholds = (NEAR_RSSI, VERY_NEAR_RSSI)
            while self.zone < 2 and self.rssi >= thresholds[self.zone] + RSSI_HYSTERESIS:
                self.zone += 1
            while self.zone > 0 and self.rssi < thresholds[self.zone - 1] - RSSI_HYSTERESIS:
                self.zone -= 1
        self.seen = now

    @property
    def label(self):
        return self.name or badge_name(self.id)

    @property
    def closeness(self):
        return signal_closeness(self.rssi)

    def visibility(self, now):
        return max(0.0, min(1.0, (FORGET_MS - (now - self.seen)) / (FORGET_MS - FADE_AFTER_MS)))

    def fresh(self, now):
        return now - self.seen < FADE_AFTER_MS

    def proximity(self, now):
        return PROXIMITY_LABELS[self.zone] if self.fresh(now) else "Fading"


class EncounterHistory:
    def __init__(self):
        self.entries = []
        self.by_id = {}
        self.dirty = False
        self.last_save = 0
        self.error = None
        saved = {"entries": []}
        try:
            State.load(HISTORY_STATE, saved)
            if not isinstance(saved["entries"], list):
                raise ValueError("entries must be a list")
            for entry in saved["entries"]:
                if not self.valid(entry):
                    raise ValueError("invalid encounter")
                if entry["id"] not in self.by_id:
                    self.entries.append(entry)
                    self.by_id[entry["id"]] = entry
                if len(self.entries) == HISTORY_LIMIT:
                    break
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.error = "History could not be loaded"
            print("Radar history load failed:", error)

    @staticmethod
    def valid(entry):
        return (
            isinstance(entry, dict)
            and isinstance(entry.get("id"), str)
            and len(entry["id"]) == 16
            and all(c in "0123456789abcdef" for c in entry["id"])
            and isinstance(entry.get("visits"), int)
            and entry["visits"] > 0
            and all(isinstance(entry.get(key), str) and len(entry[key]) <= 120
                    for key in ("name", "status", "app"))
        )

    def observe(self, peer, new_visit, text_received=False):
        key = badgelink.badge_id_hex(peer.id).lower()
        entry = self.by_id.get(key)
        if entry is None:
            entry = {"id": key, "visits": 0, "name": "", "status": "", "app": ""}
            self.by_id[key] = entry
            new_visit = True
        if new_visit:
            if entry in self.entries:
                self.entries.remove(entry)
            self.entries.insert(0, entry)
            entry["visits"] += 1
            self.dirty = True
        values = {"name": (peer.name or entry["name"] or peer.label)[:120],
                  "app": "Radar" if peer.radar else (peer.game or "Badge")}
        if text_received or not peer.radar:
            values["status"] = peer.status[:120]
        for field, value in values.items():
            if entry[field] != value:
                entry[field] = value
                self.dirty = True
        while len(self.entries) > HISTORY_LIMIT:
            removed = self.entries.pop()
            del self.by_id[removed["id"]]

    def save(self, now, force=False):
        if not self.dirty or (not force and now - self.last_save < HISTORY_SAVE_MS):
            return
        self.last_save = now
        try:
            State.save(HISTORY_STATE, {"entries": self.entries})
        except (OSError, ValueError) as error:
            self.error = "History could not be saved"
            print("Radar history save failed:", error)
            return
        self.dirty = False
        self.error = None


class HuntGame:
    def __init__(self, peer, now):
        self.target_id = peer.id
        self.name = peer.label
        self.started = now
        self.finished = None
        self.next_buzz = now
        self.trend = "Follow the signal"
        self.reference = None
        self.reference_at = now

    def update(self, peer, now, haptics):
        if self.finished is not None or peer is None or not peer.fresh(now):
            self.reference = None
            haptics.pending = False
            return
        self.name = peer.label
        if self.reference is None:
            self.reference = peer.rssi
            self.reference_at = now
            self.trend = "Follow the signal"
        elif now - self.reference_at >= 2000:
            change = peer.rssi - self.reference
            self.trend = "Warmer" if change >= 3 else ("Colder" if change <= -3 else "Steady")
            self.reference = peer.rssi
            self.reference_at = now
        if now >= self.next_buzz:
            haptics.queue()
            self.next_buzz = now + int(1800 - 1400 * peer.closeness)

    def elapsed(self, now):
        return ((self.finished if self.finished is not None else now) - self.started) // 1000


class Radar:
    def __init__(self):
        self.my_id = bytes(machine_id())[:badgelink.ID_LEN]
        self.my_name = secret("CONTACT_NAME") or badge_name(self.my_id)
        self.my_status = secret("RADAR_STATUS")
        self.codes = game_codes()
        self.peers = {}
        self.addresses = {}
        self.queue = {}
        self.dropped = 0
        self.connections = []
        self.readvertise = False
        self.rescan = False
        self.closing = False
        self.view = "radar"
        self.selected_id = None
        self.top_row = 0
        self.history_top = 0
        self.history = EncounterHistory()
        self.game = None
        self.matrix = MatrixDisplay()
        self.haptics = HapticFeedback()
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        try:
            self.ble.config(rxbuf=2048)
        except (ValueError, TypeError) as error:
            print("Radar: using the firmware's default BLE receive buffer:", error)
        self.ble.irq(self.irq)
        self.advertise()
        self.ble.gap_scan(0, SCAN_INTERVAL_US, SCAN_WINDOW_US, True)

    def advertise(self):
        flags = b"\x02\x01\x06"
        body = RADAR_MAGIC + bytes((RADAR_VERSION,)) + self.my_id
        adv = flags + bytes((len(body) + 1, 0xFF)) + body
        # "|" separates name and status, so it can't appear in the name
        name = self.my_name.replace("|", "/")
        text = utf8_cut(name, 12) + b"|" + self.my_status.encode()
        text = utf8_cut(text.decode(), TEXT_LIMIT)
        rsp_body = RADAR_TEXT + text
        rsp = bytes((len(rsp_body) + 1, 0xFF)) + rsp_body
        # Connectable on purpose: on this firmware a non-connectable advert is
        # also non-scannable, which would hide the name and status above.
        # Connections are dropped in update() and advertising restarted.
        self.ble.gap_advertise(ADV_INTERVAL_US, adv_data=adv, resp_data=rsp)

    def irq(self, event, data):
        if self.closing:
            return
        if event == IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv = data
            kind = packet_kind(adv_type, adv)
            if not kind or not -127 <= rssi < 0:
                return
            address = (addr_type, bytes(addr))
            key = (address, kind)
            if key not in self.queue and len(self.queue) >= QUEUE_LIMIT:
                self.dropped += 1
                if kind == 2:
                    return
                # Identity packets take priority over text; keep newer sightings.
                oldest = min(self.queue, key=lambda k: (k[1] != 2, self.queue[k][-1]))
                del self.queue[oldest]
            self.queue[key] = (address, adv_type, rssi, bytes(adv), badge.ticks)
        elif event == IRQ_CENTRAL_CONNECT:
            self.connections.append(data[0])
        elif event == IRQ_CENTRAL_DISCONNECT:
            self.readvertise = True
        elif event == IRQ_SCAN_DONE:
            self.rescan = True

    def keep_advertising(self):
        while self.connections:
            try:
                self.ble.gap_disconnect(self.connections.pop(0))
            except OSError:
                pass
        if self.readvertise:
            self.readvertise = False
            self.advertise()
        if self.rescan:
            self.rescan = False
            self.ble.gap_scan(0, SCAN_INTERVAL_US, SCAN_WINDOW_US, True)

    def close(self):
        self.closing = True
        try:
            self.ble.gap_scan(None)
            self.ble.gap_advertise(None)
        except OSError as error:
            print("Radar Bluetooth shutdown failed:", error)
        self.history.save(badge.ticks, force=True)
        self.matrix.close()
        self.haptics.pending = False
        badge.caselights(0)

    def handle(self, addr, adv_type, rssi, adv, now):
        badge_id = None
        game = None
        radar = False
        name = None
        status = None
        text_radar = None
        for kind, value in fields(adv):
            if kind != 0xFF:
                continue
            if adv_type != ADV_SCAN_RSP and value[:4] == STOCK_MAGIC and len(value) >= 15:
                game = self.codes.get(bytes(value[5:7]), "")
                badge_id = bytes(value[7:15])
            elif (adv_type != ADV_SCAN_RSP and value[:4] == RADAR_MAGIC
                  and len(value) >= 13 and value[4] == RADAR_VERSION):
                radar = True
                badge_id = bytes(value[5:13])
            elif adv_type == ADV_SCAN_RSP and value[:3] == STOCK_NAME:
                name = value[3:].decode("utf-8", "ignore")
                text_radar = False
            elif adv_type == ADV_SCAN_RSP and value[:4] == RADAR_TEXT:
                parts = value[4:].decode("utf-8", "ignore").split("|", 1)
                name = parts[0]
                status = parts[1] if len(parts) > 1 else ""
                text_radar = True

        if badge_id is None:
            # A scan response only carries text: match it by address
            badge_id = self.addresses.get(addr)
            if badge_id is None or adv_type != ADV_SCAN_RSP:
                return
        if badge_id == self.my_id:
            return

        peer = self.peers.get(badge_id)
        new_visit = peer is None
        if peer is None:
            if adv_type == ADV_SCAN_RSP:
                return
            peer = self.peers[badge_id] = Peer(badge_id, now)
            if self.game is None:
                self.haptics.queue()
        if adv_type == ADV_SCAN_RSP and text_radar != peer.radar:
            return
        if peer.address != addr:
            if peer.address is not None:
                self.addresses.pop(peer.address, None)
            peer.address = addr
        self.addresses[addr] = badge_id
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
        self.history.observe(peer, new_visit, adv_type == ADV_SCAN_RSP)

    def nearby(self, now):
        return sorted(
            (peer for peer in self.peers.values() if peer.rssi is not None),
            key=lambda peer: (not peer.fresh(now), -peer.rssi, peer.id),
        )

    def update(self, now):
        self.keep_advertising()
        pending, self.queue = self.queue, {}
        # Match identities before text; MicroPython dicts do not preserve arrival order.
        packets = sorted(pending.items(), key=lambda item: (item[0][1], item[1][-1], item[0][0]))
        for _, packet in packets:
            if now - packet[-1] < FORGET_MS:
                self.handle(*packet)
        if self.dropped:
            print("Radar: coalesced queue full, dropped %d packets" % self.dropped)
            self.dropped = 0
        gone = {key for key, peer in self.peers.items() if now - peer.seen >= FORGET_MS}
        if gone:
            for badge_id in gone:
                del self.peers[badge_id]
            self.addresses = {addr: badge_id for addr, badge_id in self.addresses.items() if badge_id not in gone}

        peers = self.nearby(now)
        self.handle_buttons(peers, now)

        visible = peers
        if self.game is not None:
            target = self.peers.get(self.game.target_id)
            self.game.update(target, now, self.haptics)
            visible = [target] if target is not None and self.game.finished is None else []
        if visible:
            nearest = visible[0]
            pulse = 0.75 + 0.25 * math.sin(now / 250)
            badge.caselights(nearest.closeness * nearest.visibility(now) * pulse)
        else:
            badge.caselights(0)
        self.haptics.update(now)
        self.matrix.render(visible, now)
        self.history.save(now)
        return peers

    def handle_buttons(self, peers, now):
        if self.game is not None:
            if badge.pressed(BUTTON_LEFT) or (
                self.game.finished is not None and badge.pressed(BUTTON_SELECT)
            ):
                self.game = None
                self.haptics.pending = False
                self.view = "list"
            elif badge.pressed(BUTTON_SELECT):
                self.game.finished = now
            return
        if self.view == "history":
            if badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_SELECT):
                self.view = "radar"
            else:
                self.history_top += int(badge.pressed(BUTTON_DOWN)) - int(badge.pressed(BUTTON_UP))
            self.history_top = max(0, min(self.history_top, len(self.history.entries) - VISIBLE_ROWS))
            return
        if badge.pressed(BUTTON_SELECT):
            self.view = "list" if self.view == "radar" else "radar"
            self.top_row = 0
            return
        if self.view == "radar":
            if badge.pressed(BUTTON_RIGHT):
                self.view = "history"
            return
        if badge.pressed(BUTTON_LEFT):
            self.view = "radar"
            return
        if not peers:
            self.selected_id = None
            self.top_row = 0
            return
        ids = [peer.id for peer in peers]
        selected = ids.index(self.selected_id) if self.selected_id in ids else 0
        selected += int(badge.pressed(BUTTON_DOWN)) - int(badge.pressed(BUTTON_UP))
        selected = max(0, min(selected, len(peers) - 1))
        self.selected_id = ids[selected]
        self.top_row = max(0, min(self.top_row, len(peers) - VISIBLE_ROWS))
        self.top_row = min(self.top_row, selected)
        self.top_row = max(self.top_row, selected - VISIBLE_ROWS + 1)
        if badge.pressed(BUTTON_RIGHT):
            self.game = HuntGame(peers[selected], now)
            self.haptics.pending = False

    def draw(self, peers, now):
        screen.alpha = 255
        screen.pen = black
        screen.clear()
        if self.game is not None:
            self.draw_game(now)
        elif self.view == "history":
            self.draw_history()
        elif self.view == "list":
            self.draw_list(peers, now)
        else:
            self.draw_radar(peers, now)
            self.draw_panel(peers, now)

    def draw_radar(self, peers, now):
        screen.pen = grid
        for r in (signal_radius(signal_closeness(VERY_NEAR_RSSI)),
                  signal_radius(signal_closeness(NEAR_RSSI)), RADIUS):
            screen.shape(shape.circle(CX, CY, r).stroke(1))
        centre = vec2(CX, CY)
        screen.line(vec2(CX - RADIUS, CY), vec2(CX + RADIUS, CY))
        screen.line(vec2(CX, CY - RADIUS), vec2(CX, CY + RADIUS))
        screen.font = body_font
        screen.pen = dim
        for label, y in (("Far", CY - RADIUS + 5), ("Near", CY - 58), ("Very near", CY - 35)):
            screen.text(label, CX + 6, y, 11)

        # Rotating sweep, purely decorative
        angle = (now % SWEEP_MS) / SWEEP_MS * 2 * math.pi
        screen.pen = sweep
        for step in range(8):
            a = angle - step * 0.06
            screen.line(centre, vec2(CX + math.cos(a) * RADIUS, CY + math.sin(a) * RADIUS))
        screen.pen = accent
        screen.line(centre, vec2(CX + math.cos(angle) * RADIUS, CY + math.sin(angle) * RADIUS))

        for peer in reversed(peers):
            r = signal_radius(peer.closeness)
            x = CX + math.cos(peer.angle) * r - DOT_SIZE / 2
            y = CY + math.sin(peer.angle) * r - DOT_SIZE / 2
            screen.alpha = int(peer.visibility(now) * 255)
            badgelink.draw_identicon(screen, peer.id, int(x), int(y), DOT_SIZE)

        screen.alpha = 255
        badgelink.draw_identicon(screen, self.my_id, CX - 8, CY - 8, 16)

    def draw_panel(self, peers, now):
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
            screen.text(nearest.proximity(now), PANEL_X, 138, 13)
        else:
            screen.pen = dim
            screen.text("scanning", PANEL_X, 104, 13)
        screen.text("signal only", PANEL_X, 170, 11)
        screen.text("no direction", PANEL_X, 184, 11)
        if self.history.error:
            screen.pen = accent
            screen.text("history error", PANEL_X, 200, 11)
        screen.pen = faint
        centred("select: list   right: history", 222, 12)

    def draw_list(self, peers, now):
        screen.font = body_font
        if not peers:
            screen.pen = white
            centred("no badges nearby yet", 96, 18)
            screen.pen = dim
            centred("they show up while running", 124, 14)
            centred("Radar, Contacts, Pong or Merge Conflict", 142, 14)
            screen.pen = faint
            centred("select: radar", 222, 12)
            return
        for slot, peer in enumerate(peers[self.top_row:self.top_row + VISIBLE_ROWS]):
            top = 6 + slot * (ROW_HEIGHT + 4)
            screen.pen = row_fill
            screen.rectangle(4, top, WIDTH - 8, ROW_HEIGHT)
            if peer.id == self.selected_id:
                screen.pen = accent
                screen.rectangle(4, top, 3, ROW_HEIGHT)
            screen.alpha = int(peer.visibility(now) * 255)
            badgelink.draw_identicon(screen, peer.id, 10, top + 6, ROW_HEIGHT - 12)
            screen.pen = white
            screen.text(fit(peer.label, 170, 16), 54, top + 5, 16)
            screen.pen = dim
            detail = peer.status or ("in " + peer.game if peer.game else ("Radar" if peer.radar else "Badge"))
            screen.text(fit(detail, 170, 13), 54, top + 25, 13)
            screen.pen = accent
            text = peer.proximity(now)
            w, _ = screen.measure_text(text, font_size=13)
            screen.text(text, WIDTH - 12 - w, top + 16, 13)
            screen.alpha = 255
        screen.pen = faint
        centred("up/down: pick   right: play", 208, 12)
        ids = [peer.id for peer in peers]
        selected = ids.index(self.selected_id) + 1 if self.selected_id in ids else 1
        centred("select: radar   %d / %d" % (selected, len(peers)), 224, 12)

    def draw_history(self):
        screen.font = body_font
        screen.pen = white
        screen.text("Encounters", 8, 4, 20)
        screen.pen = dim
        screen.text("%d badges" % len(self.history.entries), 224, 8, 13)
        if not self.history.entries:
            centred("No encounters recorded yet", 100, 18)
        for slot, entry in enumerate(self.history.entries[self.history_top:self.history_top + VISIBLE_ROWS]):
            top = 32 + slot * 42
            screen.pen = row_fill
            screen.rectangle(4, top, WIDTH - 8, 38)
            screen.pen = white
            screen.text(fit(entry["name"], 210, 16), 12, top + 2, 16)
            screen.pen = dim
            screen.text(fit(entry["status"] or entry["app"], 210, 12), 12, top + 22, 12)
            visits = fit("%d %s" % (entry["visits"], "visit" if entry["visits"] == 1 else "visits"), 80, 12)
            width, _ = screen.measure_text(visits, font_size=12)
            screen.text(visits, WIDTH - 12 - width, top + 12, 12)
        screen.pen = dim
        centred(self.history.error or "Recent encounters first; not contact exchanges", 206, 12)
        screen.pen = faint
        centred("up/down: scroll   left/select: radar", 224, 12)

    def draw_game(self, now):
        game = self.game
        peer = self.peers.get(game.target_id)
        screen.font = body_font
        screen.pen = accent
        centred("Hot / Cold", 8, 22)
        screen.pen = white
        centred(fit(game.name, WIDTH - 24, 24), 42, 24)
        if game.finished is not None:
            screen.pen = accent
            centred("Found!", 100, 36)
            screen.pen = dim
            centred("Meeting confirmed by you", 148, 16)
            centred("%d seconds" % game.elapsed(now), 178, 16)
            screen.pen = faint
            centred("left/select: back to list", 222, 12)
            return
        fresh = peer is not None and peer.fresh(now)
        label = ("Cold", "Warm", "Hot")[peer.zone] if fresh else (
            "Signal fading" if peer is not None else "Searching..."
        )
        screen.pen = white
        centred(label, 96, 28)
        screen.pen = row_fill
        screen.rectangle(24, 140, 272, 18)
        if peer is not None:
            screen.pen = accent
            screen.alpha = int(peer.visibility(now) * 255)
            screen.rectangle(24, 140, int(272 * peer.closeness), 18)
            screen.alpha = 255
        screen.pen = dim
        centred(game.trend if fresh else "Move around to find the signal", 170, 16)
        centred("%d seconds - signal, not direction" % game.elapsed(now), 196, 12)
        screen.pen = faint
        centred("select: found!   left: quit", 222, 12)


def machine_id():
    import machine
    return machine.unique_id()


def badge_name(badge_id):
    formatter = getattr(badgelink, "badge_name", None)
    if formatter is not None:
        return formatter(badge_id)
    return "badge " + "".join("%02x" % value for value in badge_id[-2:])


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
