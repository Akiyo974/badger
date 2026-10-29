"""
APP_TITLE: a starting point for a badge app.

MonaOS runs this file when the app is opened from the menu. The names used
below (badge, screen, color, shape, image, run, the BUTTON_ constants, HIRES
and VSYNC) are already defined by MonaOS: no import is needed for them.

What it does: a square moves with the arrows and changes colour with Select,
like a contribution square. Replace it with your own idea.
"""
import missing_details

# 320 x 240 pixels, smooth edges, drawn in sync with the screen
badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

WIDTH, HEIGHT = 320, 240
SIZE = 28
STEP = 4

background = color.rgb(13, 17, 23)
white = color.rgb(230, 237, 243)
dim = color.rgb(139, 148, 158)
# GitHub's contribution greens
GREENS = (
    color.rgb(14, 68, 41),
    color.rgb(0, 109, 50),
    color.rgb(38, 166, 65),
    color.rgb(57, 211, 83),
)

font = missing_details.mona_sans()
x, y = (WIDTH - SIZE) / 2, (HEIGHT - SIZE) / 2 + 20
level = 3


def centered(text, top, size, pen):
    width, _ = screen.measure_text(text, font_size=size)
    screen.pen = pen
    screen.text(text, (WIDTH - width) / 2, top, size)


def update():
    """Called once per frame: read the buttons, then draw the whole screen."""
    global x, y, level
    if badge.held(BUTTON_LEFT):
        x = max(0, x - STEP)
    if badge.held(BUTTON_RIGHT):
        x = min(WIDTH - SIZE, x + STEP)
    if badge.held(BUTTON_UP):
        y = max(70, y - STEP)
    if badge.held(BUTTON_DOWN):
        y = min(HEIGHT - SIZE, y + STEP)
    if badge.pressed(BUTTON_SELECT):
        level = (level + 1) % len(GREENS)

    screen.pen = background
    screen.clear()
    screen.font = font
    centered("Hello, Universe!", 14, 24, white)
    centered("arrows: move    select: colour", 46, 12, dim)
    screen.pen = GREENS[level]
    screen.shape(shape.rounded_rectangle(x, y, SIZE, SIZE, 5))


run(update)
