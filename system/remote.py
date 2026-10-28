"""
Watch remote: presses the badge's buttons from a Wear OS watch over Bluetooth.

The badge advertises a GATT service with one writable characteristic. Each
write is 2 bytes: an action (tap, down, up) and a button. The presses are
merged into the badge's real ones in badge.poll(), so every app sees them as
if the buttons had been pressed.

The remote only uses the radio while nobody else does: Contacts, Pong, Merge
Conflict and Radar take it over, and the badge reboots when they exit.
"""
import time

import bluetooth
from badgeware import radio as shared_radio

SERVICE_UUID = bluetooth.UUID("6e1d1000-8d5c-4b52-9a57-2a6b4c1b0001")
COMMAND_UUID = bluetooth.UUID("6e1d1001-8d5c-4b52-9a57-2a6b4c1b0001")
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
        self.connected = None
        self.queue = []
        self.held = {}      # button -> release deadline (ticks_ms)
        self.tapped = []    # buttons to release on the next poll
        self.retry_at = 0
        self.handler = self.irq  # one bound method, so the radio can tell it is ours
        self.name = NAME_PREFIX + badge.uid[-4:].upper()

    # Radio ----------------------------------------------------------------

    def irq(self, event, data):
        if event == IRQ_GATTS_WRITE:
            handle = data[1]
            if handle == self.handle and len(self.queue) < QUEUE_LIMIT:
                self.queue.append(bytes(self.ble.gatts_read(handle)))
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
            ((self.handle,),) = self.ble.gatts_register_services(
                ((SERVICE_UUID, ((COMMAND_UUID, bluetooth.FLAG_WRITE | bluetooth.FLAG_WRITE_NO_RESPONSE),)),)
            )
            self._advertise()
        except OSError as error:
            print("remote: radio unavailable:", error)
            self.ble = None

    # Buttons --------------------------------------------------------------

    def _merge(self, now):
        pressed = []
        released = list(self.tapped)
        self.tapped = []
        for button in released:
            self.held.pop(button, None)

        while self.queue:
            command = self.queue.pop(0)
            if len(command) < 2 or command[1] >= len(BUTTONS):
                continue
            action, button = command[0], BUTTONS[command[1]]
            if action == ACTION_UP:
                if button in self.held:
                    self.held.pop(button)
                    released.append(button)
                continue
            if button not in self.held:
                pressed.append(button)
            if action == ACTION_TAP:
                self.held[button] = now
                self.tapped.append(button)
            elif action == ACTION_DOWN:
                self.held[button] = time.ticks_add(now, HOLD_TIMEOUT_MS)

        for button, deadline in list(self.held.items()):
            if button not in self.tapped and time.ticks_diff(now, deadline) >= 0:
                self.held.pop(button)
                released.append(button)

        if not (pressed or released or self.held):
            return
        held = tuple(self.held)
        changed = tuple(pressed) + tuple(released)
        # badge.buttons are the physical buttons, badge.all adds the touch pad
        for controls in (badge.buttons, badge.all):
            controls._pressed = _union(controls._pressed, pressed)
            controls._released = _union(controls._released, released)
            controls._changed = _union(controls._changed, changed)
            controls._held = _union(controls._held, held)

    def poll(self):
        now = time.ticks_ms()
        self._claim_radio(now)
        self._merge(now)


def _union(real, extra):
    if not extra:
        return real
    return tuple(real) + tuple(button for button in extra if button not in real)


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
