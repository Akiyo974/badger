"""
Watch remote: presses the badge's buttons from a Wear OS watch over Bluetooth.

The badge advertises a GATT service with one writable characteristic. Each
write is 2 bytes: an action (tap, down, up) and a button. The presses are
merged into the badge's real ones in badge.poll(), so every app sees them as
if the buttons had been pressed.

A second characteristic receives the day's steps from the watch, each time
Badger Remote opens. They are saved in /state (watch_steps), where the
Pedometer and Mona Pet read them; the badge's own step counter is not used, as
the badge hangs around the neck.

The remote only uses the radio while nobody else does: Contacts, Pong, Merge
Conflict and Radar take it over, and the badge reboots when they exit.
"""
import struct
import time

import bluetooth
from badgeware import State
from badgeware import radio as shared_radio

SERVICE_UUID = bluetooth.UUID("6e1d1000-8d5c-4b52-9a57-2a6b4c1b0001")
COMMAND_UUID = bluetooth.UUID("6e1d1001-8d5c-4b52-9a57-2a6b4c1b0001")
STEPS_UUID = bluetooth.UUID("6e1d1002-8d5c-4b52-9a57-2a6b4c1b0001")
STEPS_STATE = "watch_steps"
NAME_PREFIX = "Badger "

IRQ_CENTRAL_CONNECT = 1
IRQ_CENTRAL_DISCONNECT = 2
IRQ_GATTS_WRITE = 3

ACTION_TAP = 0
ACTION_DOWN = 1
ACTION_UP = 2

# A held button the watch stopped talking about is released after this long.
# The watch repeats ACTION_DOWN every 500 ms while the button is held.
HOLD_TIMEOUT_MS = 1500
QUEUE_LIMIT = 16
ADV_INTERVAL_US = 250000
SECRETS_FILE = "/secrets.py"
RETRY_MS = 2000

# Steps write, little-endian: version 1, watch date and time at the sync
# (u16 year, month, day, hour, minute), u32 steps today, then the first hour
# with a count and how many hourly u16 counts follow (none if the watch has no
# history or the link is too small for them).
STEPS_VERSION = 1
STEPS_HEADER = "<BHBBBBIBB"
STEPS_BUFFER = 64
PREFERRED_MTU = 72

# badge and the buttons only exist in the namespace main.py and the apps run
# in, so start() receives them. BUTTONS lists them by code, in the same order
# as the watch app: up, down, left, right, select, back, home.
badge = None
BUTTONS = ()


def _advertisement(name):
    flags = b"\x02\x01\x06"
    uuid = bytes(SERVICE_UUID)
    adv = flags + bytes((len(uuid) + 1, 0x07)) + uuid
    encoded = name.encode()
    rsp = bytes((len(encoded) + 1, 0x09)) + encoded
    return adv, rsp


class Remote:
    def __init__(self):
        self.ble = None
        self.handle = None
        self.steps_handle = None
        self.steps_payload = None
        self.steps_version = 0  # goes up with every sync, for apps that show the steps live
        self.connected = None
        self.queue = []
        self.held = {}      # button -> release deadline (ticks_ms)
        self.tapped = []    # buttons to release on the next poll
        self.previous = [(), ()]  # combined held buttons at the last poll, per Controls
        self.retry_at = 0
        self.handler = self.irq  # one bound method, so the radio can tell it is ours
        self.name = NAME_PREFIX + badge.uid[-4:].upper()

    # Radio ----------------------------------------------------------------

    def irq(self, event, data):
        if event == IRQ_GATTS_WRITE:
            handle = data[1]
            if handle == self.handle and len(self.queue) < QUEUE_LIMIT:
                self.queue.append(bytes(self.ble.gatts_read(handle)))
            elif handle == self.steps_handle:
                # Saved on the next poll: no file writes in an interrupt
                self.steps_payload = bytes(self.ble.gatts_read(handle))
        elif event == IRQ_CENTRAL_CONNECT:
            self.connected = data[0]
        elif event == IRQ_CENTRAL_DISCONNECT:
            self.connected = None
            # Lets go of anything the watch was holding, then waits for it again
            for button in self.held:
                self.held[button] = 0
            self._advertise()

    def _advertise(self):
        adv, rsp = _advertisement(self.name)
        self.ble.gap_advertise(ADV_INTERVAL_US, adv_data=adv, resp_data=rsp, connectable=True)

    def _owns_radio(self):
        return shared_radio.radio.handler is self.handler

    def _claim_radio(self, now):
        """Takes the radio back when no app holds it."""
        radio = shared_radio.radio
        if self._owns_radio():
            return
        if radio.handler is not None:
            self.ble = None
            self.connected = None
            return
        if time.ticks_diff(now, self.retry_at) < 0:
            return
        self.retry_at = time.ticks_add(now, RETRY_MS)
        try:
            self.ble = radio.open(self.handler)
            ((self.handle, self.steps_handle),) = self.ble.gatts_register_services(
                ((SERVICE_UUID, (
                    (COMMAND_UUID, bluetooth.FLAG_WRITE | bluetooth.FLAG_WRITE_NO_RESPONSE),
                    (STEPS_UUID, bluetooth.FLAG_WRITE),
                )),)
            )
            # The hourly counts need more than the default 20 bytes
            self.ble.gatts_set_buffer(self.steps_handle, STEPS_BUFFER)
            try:
                self.ble.config(mtu=PREFERRED_MTU)
            except (OSError, ValueError):
                pass
            self._advertise()
        except OSError as error:
            print("remote: radio unavailable:", error)
            self.ble = None

    # Buttons --------------------------------------------------------------

    def _update_remote(self, now):
        """Applies the queued commands to self.held, the buttons the watch holds."""
        # A tap is held for one poll, then let go
        touched = list(self.tapped)
        for button in self.tapped:
            self.held.pop(button, None)
        self.tapped = []

        # One change per button and poll: later commands for it wait, so quick
        # taps (the crown sends several at once) stay separate presses
        while self.queue:
            command = self.queue[0]
            if len(command) < 2 or command[1] >= len(BUTTONS):
                self.queue.pop(0)
                continue
            action, button = command[0], BUTTONS[command[1]]
            if button in touched:
                break
            self.queue.pop(0)
            touched.append(button)
            if action == ACTION_UP:
                self.held.pop(button, None)
            elif action == ACTION_TAP:
                self.held[button] = now
                self.tapped.append(button)
            elif action == ACTION_DOWN:
                self.held[button] = time.ticks_add(now, HOLD_TIMEOUT_MS)

        for button, deadline in list(self.held.items()):
            if button not in self.tapped and time.ticks_diff(now, deadline) >= 0:
                self.held.pop(button)

    def _merge(self):
        """Merges the watch's buttons with the real ones.

        Edges come from the combined state, so a button held on the badge and
        on the watch at once is pressed once and released only when both let go.
        """
        remote = list(self.held)
        # badge.buttons are the physical buttons, badge.all adds the touch pad
        for index, controls in enumerate((badge.buttons, badge.all)):
            before = self.previous[index]
            real = controls._held
            if not remote and all(button in real for button in before):
                self.previous[index] = tuple(real)
                continue
            held = tuple(real) + tuple(button for button in remote if button not in real)
            pressed = [button for button in held if button not in before]
            pressed += [button for button in controls._pressed if button not in before and button not in pressed]
            released = [button for button in before if button not in held]
            released += [button for button in controls._released if button not in held and button not in released]
            controls._held = held
            controls._pressed = tuple(pressed)
            controls._released = tuple(released)
            controls._changed = tuple(pressed) + tuple(released)
            self.previous[index] = held

    # Steps ----------------------------------------------------------------

    def _save_steps(self):
        payload, self.steps_payload = self.steps_payload, None
        record = parse_steps(payload)
        if record is None:
            print("remote: steps ignored:", payload)
            return
        State.save(STEPS_STATE, record)
        self.steps_version += 1

    def poll(self):
        now = time.ticks_ms()
        self._claim_radio(now)
        self._update_remote(now)
        self._merge()
        if self.steps_payload is not None:
            self._save_steps()


def parse_steps(payload):
    """The record saved in /state from a steps write, or None if it is not one."""
    size = struct.calcsize(STEPS_HEADER)
    if len(payload) < size:
        return None
    version, year, month, day, hour, minute, steps, first_hour, count = struct.unpack_from(STEPS_HEADER, payload)
    if version != STEPS_VERSION or not (1 <= month <= 12 and 1 <= day <= 31 and hour < 24 and minute < 60):
        return None
    if first_hour + count > 24 or len(payload) < size + 2 * count:
        count = 0
    hours = list(struct.unpack_from("<%dH" % count, payload, size)) if count else []
    return {
        "date": [year, month, day],
        "synced": [hour, minute],
        "steps": steps,
        "first_hour": first_hour if count else 0,
        "hours": hours,
    }


remote = None


def enabled():
    """WATCH_REMOTE = False in secrets.py turns the remote off."""
    # Read without importing, so the apps still get a fresh secrets module
    settings = {}
    try:
        with open(SECRETS_FILE) as file:
            exec(file.read(), settings)
    except (OSError, SyntaxError):
        return True
    return settings.get("WATCH_REMOTE", True)


def start(the_badge, buttons):
    """Wraps badge.poll() so every app sees the watch's presses."""
    global remote, badge, BUTTONS
    if remote is not None:
        return remote
    badge, BUTTONS = the_badge, tuple(buttons)
    remote = Remote()
    real_poll = badge.poll

    def poll(*args):
        result = real_poll(*args)
        try:
            remote.poll()
        except Exception as error:  # noqa: BLE001
            print("remote:", error)
        return result

    badge.poll = poll
    return remote
