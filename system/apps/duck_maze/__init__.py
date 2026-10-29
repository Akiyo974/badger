"""
Duck Maze: tilt the badge to roll a marble through a maze drawn like a
contribution graph. Collect every rubber duck to open the merge, and keep out
of the bug holes. Six levels, each one unlocking the next, with best times.

Hold the badge the way you want to play when you press Select: that position
is "flat", and tilting away from it rolls the marble.

Controls:
* Left / Right = choose a level (title screen)
* Select = play / next level
* Back = back to the title
"""
import math
import os
import sys

import missing_details
from badgeware import State

APP_DIR = "/system/apps/duck_maze"
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

import levels  # noqa: E402

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2
# The game redraws only what moves, so the frame must not be cleared for it
badge.default_clear = None

STATE_KEY = "duck_maze"

CELL = 20
TOP = 20  # status bar height
BALL_R = 6
HOLE_R = 7  # the marble falls once its centre is this close to a hole's
PICK_R = 10
EXIT_R = 9

# Tilt → acceleration. Readings are raw, 16384 = 1 g.
G = 16384
ROLL_PX = 950  # px/s² for a tilt of one g
DEADZONE = 0.03
DRAG = 1.1  # per second
BOUNCE = 0.35
MAX_SPEED = 320
STEP_PX = 3  # sub-step size, so a fast marble cannot pass through a wall
# Signs of the two tilt axes, set on the badge so tilting "down" rolls down
TILT_X_SIGN = 1
TILT_Y_SIGN = 1

FALL_MS = 1200
TRAIL = 6

background = color.rgb(13, 17, 23)
panel = color.rgb(22, 27, 34)
white = color.rgb(235, 245, 255)
dim = color.rgb(139, 148, 158)
faint = color.rgb(48, 54, 61)
phosphor = color.rgb(211, 250, 55)
bug_red = color.rgb(248, 81, 73)
hole_black = color.rgb(4, 6, 8)
marble = color.rgb(198, 212, 228)
marble_shade = color.rgb(120, 138, 160)
marble_glint = color.rgb(255, 255, 255)
shadow = color.rgb(0, 0, 0, 120)
# The four greens of a GitHub contribution graph, for the walls
WALL_GREENS = (
    color.rgb(14, 68, 41),
    color.rgb(0, 109, 50),
    color.rgb(38, 166, 65),
    color.rgb(57, 211, 83),
)

font_body = missing_details.mona_sans()


def text(value, x, y, size, pen, centre=False):
    screen.pen = pen
    if centre:
        width, _ = screen.measure_text(value, font_size=size)
        x -= width / 2
    screen.text(value, x, y, size)


def seconds(ms):
    return "%.1fs" % (ms / 1000)


class Tilt:
    """Tilt relative to the position held when the level started."""

    def __init__(self):
        self.rest_x = 0
        self.rest_pitch = 0

    @staticmethod
    def pitch(ay, az):
        # Angle of gravity around the screen's horizontal axis: 0 flat, 90° upright
        return math.atan2(ay, -az)

    def calibrate(self, reading):
        ax, ay, az = reading[:3]
        self.rest_x = ax
        self.rest_pitch = self.pitch(ay, az)

    def read(self, reading):
        ax, ay, az = reading[:3]
        x = TILT_X_SIGN * (ax - self.rest_x) / G
        y = TILT_Y_SIGN * math.sin(self.pitch(ay, az) - self.rest_pitch)
        x = 0 if abs(x) < DEADZONE else x
        y = 0 if abs(y) < DEADZONE else y
        return max(-1, min(1, x)), max(-1, min(1, y))


class Level:
    def __init__(self, number):
        self.number = number
        self.name, rows = levels.LEVELS[number]
        self.walls, self.holes, ducks, start, self.exit = levels.parse(rows)
        self.ducks = set(ducks)
        self.total_ducks = len(ducks)
        # Fixed shade per wall cell, so the walls read like a contribution graph
        self.wall_cells = [
            (x, y, WALL_GREENS[(x * 7 + y * 13 + number * 5) % len(WALL_GREENS)])
            for x, y in sorted(self.walls)
        ]
        self.x, self.y = self.centre(start)
        self.vx = self.vy = 0.0
        self.trail = []
        self.backdrop = None
        self.dirty = None  # spots drawn last frame, restored before the next one
        self.status = None

    @staticmethod
    def centre(cell):
        return cell[0] * CELL + CELL / 2, TOP + cell[1] * CELL + CELL / 2

    @property
    def open(self):
        return not self.ducks

    def step(self, tilt, dt):
        """Moves the marble; returns "hole", "exit" or None."""
        tx, ty = tilt
        self.vx += tx * ROLL_PX * dt
        self.vy += ty * ROLL_PX * dt
        drag = math.exp(-DRAG * dt)
        self.vx *= drag
        self.vy *= drag
        speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
        if speed > MAX_SPEED:
            self.vx *= MAX_SPEED / speed
            self.vy *= MAX_SPEED / speed

        distance = max(abs(self.vx), abs(self.vy)) * dt
        steps = max(1, int(distance / STEP_PX) + 1)
        for _ in range(steps):
            self.x += self.vx * dt / steps
            self.y += self.vy * dt / steps
            self.collide()

        self.trail.append((self.x, self.y))
        del self.trail[:-TRAIL]

        for duck in list(self.ducks):
            cx, cy = self.centre(duck)
            if (self.x - cx) ** 2 + (self.y - cy) ** 2 < PICK_R * PICK_R:
                self.ducks.discard(duck)
        for hole in self.holes:
            cx, cy = self.centre(hole)
            if (self.x - cx) ** 2 + (self.y - cy) ** 2 < HOLE_R * HOLE_R:
                self.x, self.y = cx, cy
                return "hole"
        cx, cy = self.centre(self.exit)
        if self.open and (self.x - cx) ** 2 + (self.y - cy) ** 2 < EXIT_R * EXIT_R:
            return "exit"
        return None

    def collide(self):
        # Circle against the wall squares around it, pushed out along the
        # normal, so corners are smooth and the marble bounces off walls
        first_x = int((self.x - BALL_R) // CELL)
        last_x = int((self.x + BALL_R) // CELL)
        first_y = int((self.y - TOP - BALL_R) // CELL)
        last_y = int((self.y - TOP + BALL_R) // CELL)
        for cy in range(first_y, last_y + 1):
            for cx in range(first_x, last_x + 1):
                if (cx, cy) not in self.walls:
                    continue
                left, top = cx * CELL, TOP + cy * CELL
                near_x = min(max(self.x, left), left + CELL)
                near_y = min(max(self.y, top), top + CELL)
                dx, dy = self.x - near_x, self.y - near_y
                gap2 = dx * dx + dy * dy
                if gap2 >= BALL_R * BALL_R:
                    continue
                gap = math.sqrt(gap2)
                if gap < 0.001:
                    nx, ny = 0.0, -1.0
                else:
                    nx, ny = dx / gap, dy / gap
                push = BALL_R - gap
                self.x += nx * push
                self.y += ny * push
                towards = self.vx * nx + self.vy * ny
                if towards < 0:
                    self.vx -= (1 + BOUNCE) * towards * nx
                    self.vy -= (1 + BOUNCE) * towards * ny

    def build_backdrop(self):
        # Walls and holes never move: drawn once into an off-screen image and
        # copied each frame, which keeps the marble smooth (~100 walls)
        backdrop = image(screen.width, screen.height - TOP)
        backdrop.antialias = image.X2
        backdrop.pen = background
        backdrop.clear()
        for x, y, green in self.wall_cells:
            backdrop.pen = green
            backdrop.shape(shape.rounded_rectangle(x * CELL + 1, y * CELL + 1, CELL - 2, CELL - 2, 3))
        for hole in self.holes:
            cx, cy = self.centre(hole)
            cy -= TOP
            backdrop.pen = bug_red
            backdrop.shape(shape.circle(cx, cy, HOLE_R + 1))
            backdrop.pen = hole_black
            backdrop.shape(shape.circle(cx, cy, HOLE_R - 1))
            # Little bug legs on the rim
            backdrop.pen = bug_red
            for side in (-1, 1):
                backdrop.shape(shape.rectangle(cx + side * (HOLE_R + 1) - 1, cy - 3, 2, 2))
                backdrop.shape(shape.rectangle(cx + side * (HOLE_R + 1) - 1, cy + 1, 2, 2))
        return backdrop

    def draw(self, now, duck_sheet, ball_scale=1.0, full=False):
        """Draws the maze. Copying the whole backdrop costs ~20 ms, so after the
        first frame only the spots that move (marble, trail, ducks, exit) are
        restored from it and redrawn."""
        if self.backdrop is None:
            self.backdrop = self.build_backdrop()
            full = True
        if full or self.dirty is None:
            screen.blit(self.backdrop, rect(0, TOP, screen.width, screen.height - TOP))
        else:
            for left, top, width, height in self.dirty:
                self.restore(left, top, width, height)
        self.dirty = []

        cx, cy = self.centre(self.exit)
        self.dirty.append((cx - EXIT_R - 1, cy - EXIT_R - 1, EXIT_R * 2 + 3, EXIT_R * 2 + 3))
        if self.open:
            glow = 0.6 + 0.4 * math.sin(now / 160)
            screen.pen = color.rgb(int(211 * glow), int(250 * glow), int(55 * glow))
            screen.shape(shape.circle(cx, cy, EXIT_R))
            screen.pen = background
            screen.shape(shape.circle(cx, cy, EXIT_R - 3))
            screen.pen = phosphor
            screen.shape(shape.circle(cx, cy, 3))
        else:
            screen.pen = faint
            screen.shape(shape.circle(cx, cy, EXIT_R))
            screen.pen = background
            screen.shape(shape.circle(cx, cy, EXIT_R - 2))

        if duck_sheet:
            frame = (now // 220) % 3
            for duck in self.ducks:
                dx, dy = self.centre(duck)
                left, top = int(dx) - 6, int(dy) - 6
                screen.blit(duck_sheet.sprite(frame, 0), rect(left, top, 12, 12))
                self.dirty.append((left, top, 12, 12))

        for index, (tx, ty) in enumerate(self.trail[:-1]):
            screen.pen = color.rgb(198, 212, 228, 20 + index * 12)
            screen.shape(shape.circle(tx, ty, 2))
            self.dirty.append((int(tx) - 3, int(ty) - 3, 7, 7))

        radius = BALL_R * ball_scale
        if radius > 0.5:
            screen.pen = shadow
            screen.shape(shape.circle(self.x + 1, self.y + 2, radius))
            screen.pen = marble_shade
            screen.shape(shape.circle(self.x, self.y, radius))
            screen.pen = marble
            screen.shape(shape.circle(self.x - radius * 0.15, self.y - radius * 0.15, radius * 0.8))
            screen.pen = marble_glint
            screen.shape(shape.circle(self.x - radius * 0.35, self.y - radius * 0.35, max(1, radius * 0.25)))
        self.dirty.append((int(self.x) - BALL_R - 2, int(self.y) - BALL_R - 2, BALL_R * 2 + 6, BALL_R * 2 + 7))

    def restore(self, left, top, width, height):
        # Clip to the maze area, then copy that patch of the backdrop back
        left, top = max(0, left), max(TOP, top)
        right, bottom = min(screen.width, left + width), min(screen.height, top + height)
        if right > left and bottom > top:
            screen.blit(self.backdrop, rect(left, top - TOP, right - left, bottom - top), rect(left, top, right - left, bottom - top))

    def draw_status(self, elapsed, duck_sheet, full=False):
        found = self.total_ducks - len(self.ducks)
        key = (seconds(elapsed), found)
        if key == self.status and not full:
            return
        self.status = key
        screen.pen = panel
        screen.rectangle(0, 0, screen.width, TOP)
        screen.font = font_body
        text("%d · %s" % (self.number + 1, self.name), 6, 3, 13, white)
        if duck_sheet:
            screen.blit(duck_sheet.sprite(0, 0), rect(186, 4, 12, 12))
        text("%d/%d" % (found, self.total_ducks), 202, 3, 13, phosphor if self.open else white)
        text(key[0], screen.width - 6 - screen.measure_text(key[0], font_size=13)[0], 3, 13, dim)


class Game:
    def __init__(self):
        saved = {"unlocked": 1, "best": {}}
        State.load(STATE_KEY, saved)
        self.unlocked = max(1, min(len(levels.LEVELS), int(saved.get("unlocked") or 1)))
        self.best = {str(k): int(v) for k, v in (saved.get("best") or {}).items()}
        self.choice = self.unlocked - 1
        self.mode = "title"
        self.level = None
        self.started = 0
        self.finished = 0
        self.mode_at = 0
        self.tilt = Tilt()
        self.new_best = False
        try:
            self.ducks = image.load(APP_DIR + "/duck.png").spritesheet(3, 1)
        except (OSError, ValueError) as error:
            print("Duck Maze: duck sprite unavailable:", error)
            self.ducks = None

    def save(self):
        State.save(STATE_KEY, {"unlocked": self.unlocked, "best": self.best})

    def start(self, number, now):
        self.level = Level(number)
        self.tilt.calibrate(badge.imu())
        self.started = now
        self.mode = "play"
        self.mode_at = now

    def update(self, now, dt):
        if self.mode == "title":
            self.title_frame(now)
        elif self.mode == "play":
            self.play_frame(now, dt)
        elif self.mode == "fall":
            self.fall_frame(now)
        elif self.mode in ("clear", "won"):
            self.clear_frame(now)

    def title_frame(self, now):
        if badge.pressed(BUTTON_RIGHT):
            self.choice = min(self.unlocked - 1, self.choice + 1)
        if badge.pressed(BUTTON_LEFT):
            self.choice = max(0, self.choice - 1)
        if badge.pressed(BUTTON_SELECT):
            self.start(self.choice, now)
            return
        if badge.pressed(BUTTON_BACK):
            reset()
        self.draw_title(now)

    def play_frame(self, now, dt):
        if badge.pressed(BUTTON_BACK):
            self.mode = "title"
            self.level.dirty = None
            return
        result = self.level.step(self.tilt.read(badge.imu()), dt)
        if result == "hole":
            self.mode = "fall"
            self.mode_at = now
        elif result == "exit":
            self.finish(now)
        self.level.draw(now, self.ducks)
        self.level.draw_status(now - self.started, self.ducks)

    def fall_frame(self, now):
        progress = min(1.0, (now - self.mode_at) / (FALL_MS * 0.4))
        self.level.draw(now, self.ducks, ball_scale=1 - progress, full=True)
        self.level.draw_status(now - self.started, self.ducks, full=True)
        self.banner("bug!", "back to the start", bug_red)
        if now - self.mode_at > FALL_MS:
            self.start(self.level.number, now)

    def finish(self, now):
        self.finished = now - self.started
        key = str(self.level.number)
        self.new_best = key not in self.best or self.finished < self.best[key]
        if self.new_best:
            self.best[key] = self.finished
        if self.level.number + 1 < len(levels.LEVELS):
            self.unlocked = max(self.unlocked, self.level.number + 2)
            self.mode = "clear"
        else:
            self.mode = "won"
        self.save()
        self.mode_at = now

    def clear_frame(self, now):
        self.level.draw(now, self.ducks, ball_scale=0, full=True)
        self.level.draw_status(self.finished, self.ducks, full=True)
        if self.mode == "won":
            total = sum(self.best.get(str(i), 0) for i in range(len(levels.LEVELS)))
            self.banner("all merged!", "best total " + seconds(total), phosphor, "Select: title")
        else:
            detail = seconds(self.finished) + ("  ·  new best!" if self.new_best else "")
            self.banner("merged!", detail, phosphor, "Select: next level")
        if now - self.mode_at < 400:
            return
        if badge.pressed(BUTTON_SELECT):
            if self.mode == "won":
                self.mode = "title"
                self.choice = 0
            else:
                self.choice = self.level.number + 1
                self.start(self.choice, now)
        elif badge.pressed(BUTTON_BACK):
            self.choice = min(self.level.number + 1, self.unlocked - 1)
            self.mode = "title"

    def banner(self, title, detail, pen, hint=None):
        screen.pen = color.rgb(13, 17, 23, 225)
        screen.shape(shape.rounded_rectangle(40, 80, 240, 92 if hint else 76, 8))
        screen.font = font_body
        text(title, 160, 88, 30, pen, centre=True)
        text(detail, 160, 126, 15, white, centre=True)
        if hint:
            text(hint, 160, 150, 13, dim, centre=True)

    def draw_title(self, now):
        screen.pen = background
        screen.clear()
        # A strip of contribution squares along the top and bottom
        for x in range(16):
            for y in (0, 11):
                green = WALL_GREENS[(x * 3 + y + now // 600) % len(WALL_GREENS)]
                screen.pen = green
                screen.shape(shape.rounded_rectangle(x * CELL + 1, y * CELL + 1, CELL - 2, CELL - 2, 3))

        screen.font = font_body
        text("duck maze", 160, 30, 40, white, centre=True)
        text("tilt the badge, collect the ducks, merge", 160, 74, 13, dim, centre=True)

        if self.ducks:
            bob = (now // 220) % 3
            screen.blit(self.ducks.sprite(bob, 0), rect(118, 96, 36, 36))
        screen.pen = marble_shade
        screen.shape(shape.circle(186, 118, 14))
        screen.pen = marble
        screen.shape(shape.circle(184, 116, 11))
        screen.pen = marble_glint
        screen.shape(shape.circle(180, 112, 4))

        name = levels.LEVELS[self.choice][0]
        arrows = ("< " if self.choice > 0 else "  ") + "%d · %s" % (self.choice + 1, name) + (" >" if self.choice < self.unlocked - 1 else "  ")
        text(arrows, 160, 146, 18, phosphor, centre=True)
        best = self.best.get(str(self.choice))
        text("best " + seconds(best) if best else "no time yet", 160, 170, 13, dim, centre=True)
        text("hold the badge how you'll play, then Select", 160, 196, 12, faint if now // 700 % 2 else dim, centre=True)


game = Game()
last_ticks = None


def update():
    global last_ticks
    now = badge.ticks
    dt = 0 if last_ticks is None else min(now - last_ticks, 50) / 1000
    last_ticks = now
    game.update(now, dt)


run(update)
