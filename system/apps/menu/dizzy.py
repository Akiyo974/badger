"""Shake the badge on the menu and Mona gets dizzy: X eyes, rubber ducks
circling her head. Sprites drawn by tools/make_dizzy_sprites.py."""
import math

import missing_details

DIZZY_SHEET = "/system/apps/menu/mona-dizzy.png"
DIZZY_FRAMES = 4
DUCK_SHEET = "/system/apps/menu/duck.png"
DUCK_FRAMES = 4  # 2 facing right, then the same 2 facing left
DIZZY_MS = 3500
COOLDOWN_MS = 1500
SCALE = 4

# A shake shows up three ways: the LSM6DS3's "significant motion" event, a
# burst of tap events, or jolts in the raw readings (16384 = 1 g)
EVENT_SINGLE_TAP = 1
EVENT_DOUBLE_TAP = 2
EVENT_SIGNIFICANT_MOTION = 16
SHAKE_WINDOW_MS = 1500
SHAKE_TAPS = 4
JOLT_ACCEL = 9000
JOLT_GYRO = 20000
JOLT_WINDOW_MS = 1000
JOLT_SPACING_MS = 80
SHAKE_JOLTS = 3

DUCK_COUNT = 3
DUCK_ORBIT = (50, 10)  # horizontal and vertical radius, in pixels, around her head
DUCK_TURN_MS = 1100
MONA_TOP = 64


class DizzyMona:
    def __init__(self):
        self.taps = []
        self.jolts = []
        self.until = 0
        self.quiet_until = 0
        self.mona = None
        self.duck = None
        self.font = None

    def shaken(self, now, events, reading):
        """True once per shake; nothing while playing or just after."""
        ax, ay, az, gx, gy, gz = reading
        accel = math.sqrt(ax * ax + ay * ay + az * az)
        if abs(accel - 16384) > JOLT_ACCEL or max(abs(gx), abs(gy), abs(gz)) > JOLT_GYRO:
            if not self.jolts or now - self.jolts[-1] > JOLT_SPACING_MS:
                self.jolts.append(now)
        self.jolts = [at for at in self.jolts if now - at < JOLT_WINDOW_MS]

        motion = False
        for event in events:
            if event == EVENT_SIGNIFICANT_MOTION:
                motion = True
            elif event in (EVENT_SINGLE_TAP, EVENT_DOUBLE_TAP):
                self.taps.append(now)
        self.taps = [at for at in self.taps if now - at < SHAKE_WINDOW_MS]

        if self.active(now) or now < self.quiet_until:
            return False
        if motion or len(self.taps) >= SHAKE_TAPS or len(self.jolts) >= SHAKE_JOLTS:
            self.taps = []
            self.jolts = []
            return True
        return False

    def trigger(self, now):
        self.until = now + DIZZY_MS
        self.quiet_until = self.until + COOLDOWN_MS

    def stop(self, now):
        self.until = 0
        self.quiet_until = now + COOLDOWN_MS

    def active(self, now):
        return now < self.until

    def load(self):
        if self.mona is None:
            try:
                self.mona = image.load(DIZZY_SHEET).spritesheet(DIZZY_FRAMES, 1)
                self.duck = image.load(DUCK_SHEET).spritesheet(DUCK_FRAMES, 1)
            except (OSError, ValueError) as error:
                print("Menu dizzy sprites unavailable:", error)
                self.mona = self.duck = False
            self.font = missing_details.mona_sans()

    def draw(self, now):
        self.load()
        screen.pen = color.rgb(0, 0, 0)
        screen.clear()

        left = (screen.width - 28 * SCALE) // 2
        # The ducks circle the top of her head like a halo, so the front ones
        # pass over her ears and forehead without hiding the X eyes
        centre_x, centre_y = screen.width // 2, MONA_TOP + 3 * SCALE
        ducks = []
        for index in range(DUCK_COUNT):
            angle = now / DUCK_TURN_MS * 2 * math.pi + index * 2 * math.pi / DUCK_COUNT
            front = math.sin(angle) > 0
            # In front they move left, behind they move right
            facing = 2 if front else 0
            flap = (now // 150 + index) % 2
            size = 3 if front else 2
            x = centre_x + math.cos(angle) * DUCK_ORBIT[0] - 6 * size
            y = centre_y + math.sin(angle) * DUCK_ORBIT[1] - 5 * size
            ducks.append((front, int(x), int(y), size, facing + flap))

        if self.duck:
            for front, x, y, size, frame in ducks:
                if not front:
                    screen.blit(self.duck.sprite(frame, 0), rect(x, y, 12 * size, 10 * size))
        if self.mona:
            sprite = self.mona.sprite((now // 140) % DIZZY_FRAMES, 0)
            screen.blit(sprite, rect(left, MONA_TOP, 28 * SCALE, 24 * SCALE))
        if self.duck:
            for front, x, y, size, frame in ducks:
                if front:
                    screen.blit(self.duck.sprite(frame, 0), rect(x, y, 12 * size, 10 * size))

        # The menu draws with NON_ZERO, which fills the holes of "o" and "a"
        fill_rule = screen.fill_rule
        screen.fill_rule = image.EVEN_ODD
        screen.font = self.font
        screen.pen = color.rgb(235, 245, 255)
        text = "whoa, too much shaking!"
        width, _ = screen.measure_text(text, font_size=22)
        screen.text(text, (screen.width - width) / 2, 178, 22)
        screen.fill_rule = fill_rule
