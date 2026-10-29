"""
Pedometer: the day's steps, as counted by the watch.

The badge hangs around the neck, so its own step counter is not used: Badger
Remote sends the watch's steps each time it opens on the watch, and the badge
keeps the last ones it received (/state/watch_steps), with when they came.

The hourly squares only show the hours the watch recorded; before that, the
screen says when the steps were synced instead.
"""
import sys

import missing_details
from badgeware import State

try:
    import secrets
except ImportError:
    secrets = None

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

STEPS_STATE = "watch_steps"
GOAL = 6000
STRIDE_M = 0.75
# GitHub Universe '26: October 28 and 29, 2026
UNIVERSE_DAY_ONE = (2026, 10, 28)
UNIVERSE_DAYS = 2
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
RELOAD_MS = 5000
MAX_HOURS = 12

WIDTH = 320
GRID_PITCH = 35.5
GRID_TILE = 31
HOUR_TILE = 19
HOUR_PITCH = 20
HOURS_Y = 134

black = color.rgb(0, 0, 0)
white = color.rgb(240, 244, 246)
grey = color.rgb(150, 156, 160)
dim = color.rgb(95, 100, 104)
green = color.rgb(143, 201, 58)
tile = color.rgb(14, 17, 15)
tile_lit = color.rgb(15, 44, 22)
track = color.rgb(36, 39, 41)
fill = color.rgb(57, 211, 83)
# GitHub's contribution greens, from no steps to a busy hour
LEVELS = (
    color.rgb(30, 34, 36),
    color.rgb(14, 68, 41),
    color.rgb(0, 109, 50),
    color.rgb(38, 166, 65),
    color.rgb(57, 211, 83),
)

mona_sans = missing_details.mona_sans()


def setting(key, default):
    return getattr(secrets, key, default) if secrets else default


goal = setting("STEPS_GOAL", GOAL)


def load():
    record = {}
    State.load(STEPS_STATE, record)
    return record or None


def sync_version():
    """Goes up when the watch sends new steps while the app is open."""
    remote = sys.modules.get("remote")
    return remote.remote.steps_version if remote and remote.remote else 0


def grouped(number):
    """4213 -> '4 213', like the mock-up."""
    digits = str(number)
    groups = []
    while len(digits) > 3:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    groups.insert(0, digits)
    return " ".join(groups)


def days_from(start, date):
    """Whole days from one (year, month, day) to another, for nearby dates."""
    def ordinal(year, month, day):
        lengths = (31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
        return year * 366 + sum(lengths[:month - 1]) + day
    return ordinal(*date) - ordinal(*start)


def title(record):
    if record is None:
        return "GitHub Universe '26"
    year, month, day = record["date"]
    number = days_from(UNIVERSE_DAY_ONE, (year, month, day)) + 1
    if year == UNIVERSE_DAY_ONE[0] and 1 <= number <= UNIVERSE_DAYS:
        return "GitHub Universe '26 · Day %d" % number
    return "%s %d" % (MONTHS[month - 1], day)


def synced_line(record):
    hour, minute = record["synced"]
    return "synced %02d:%02d from Galaxy Watch" % (hour, minute)


def centered(text, y, size, pen):
    w, _ = screen.measure_text(text, font_size=size)
    if w > WIDTH - 16:
        size = size * (WIDTH - 16) / w
        w = WIDTH - 16
    screen.pen = pen
    screen.text(text, WIDTH / 2 - w / 2, y, size)


def draw_grid():
    """The dark tiles behind everything, a few of them lit like contributions."""
    for row in range(7):
        for column in range(9):
            lit = (column * 7 + row * 13) % 11 == 0
            screen.pen = tile_lit if lit else tile
            screen.shape(shape.rounded_rectangle(2 + column * GRID_PITCH, 2 + row * GRID_PITCH, GRID_TILE, GRID_TILE, 3))


def visible_hours(record):
    """(first hour, counts) for the squares, at most MAX_HOURS, latest last."""
    hours = record.get("hours") or []
    first = record.get("first_hour", 0)
    if len(hours) > MAX_HOURS:
        first += len(hours) - MAX_HOURS
        hours = hours[-MAX_HOURS:]
    return first, hours


def level(count, busiest):
    if count <= 0 or busiest <= 0:
        return LEVELS[0]
    return LEVELS[min(len(LEVELS) - 1, 1 + int(count * (len(LEVELS) - 1) / (busiest + 1)))]


def draw_hours(record):
    first, hours = visible_hours(record)
    if not hours:
        # No hourly history from the watch: say where the number comes from
        centered(synced_line(record), HOURS_Y + 4, 13, grey)
        return False
    busiest = max(hours)
    left = WIDTH / 2 - (len(hours) * HOUR_PITCH - (HOUR_PITCH - HOUR_TILE)) / 2
    for index, count in enumerate(hours):
        x = left + index * HOUR_PITCH
        screen.pen = level(count, busiest)
        screen.shape(shape.rounded_rectangle(x, HOURS_Y, HOUR_TILE, HOUR_TILE, 3))
        label = str(first + index)
        w, _ = screen.measure_text(label, font_size=8)
        screen.pen = dim
        screen.text(label, x + HOUR_TILE / 2 - w / 2, HOURS_Y + HOUR_TILE + 2, 8)
    return True


def draw_progress(steps):
    km = steps * STRIDE_M / 1000
    screen.pen = white
    distance = "%.1f km" % km
    screen.text(distance, 18, 180, 12)
    w, _ = screen.measure_text(distance, font_size=12)
    screen.pen = grey
    screen.text(" walked", 18 + w, 180, 12)

    target = grouped(goal)
    tw, _ = screen.measure_text(target, font_size=12)
    lw, _ = screen.measure_text("goal ", font_size=12)
    screen.text("goal ", WIDTH - 18 - tw - lw, 180, 12)
    screen.pen = white
    screen.text(target, WIDTH - 18 - tw, 180, 12)

    screen.pen = track
    screen.shape(shape.rounded_rectangle(18, 201, WIDTH - 36, 5, 2))
    done = min(1, steps / goal) if goal else 0
    if done > 0:
        screen.pen = fill
        screen.shape(shape.rounded_rectangle(18, 201, max(5, (WIDTH - 36) * done), 5, 2))


def draw(record):
    screen.pen = black
    screen.clear()
    draw_grid()
    screen.font = mona_sans

    centered(title(record), 14, 13, grey)
    if record is None:
        centered("-", 40, 56, white)
        centered("no steps yet", 104, 15, green)
        centered("open Badger Remote on your watch", HOURS_Y + 4, 13, grey)
        draw_progress(0)
        return

    steps = record["steps"]
    centered(grouped(steps), 34, 60, white)
    centered("steps today", 102, 15, green)
    if draw_hours(record):
        centered(synced_line(record), 220, 10, dim)
    draw_progress(steps)


record = load()
version = sync_version()
reload_at = 0


def update():
    global record, version, reload_at
    # The watch may sync while the app is open
    now = badge.ticks
    current = sync_version()
    if current != version or now >= reload_at:
        version = current
        reload_at = now + RELOAD_MS
        record = load()
    draw(record)


run(update)
