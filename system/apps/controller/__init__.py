"""
Controller: the badge as a game pad for a computer, over the USB cable.

Each press and release of ↑ ↓ ← → Select and Back is printed on the serial
port as one line, "+up" when pressed and "-up" when let go. On the computer,
tools/badge_controller.py turns those lines into key presses for any game or
program; your own code can read them too (docs/guides/controller.md).

Presses from the Badger Remote watch arrive here like real ones, so the watch
can drive the computer through the badge. Home leaves the app.
"""
import missing_details

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

WIDTH, HEIGHT = 320, 240
# The name sent for each button: also the keys of tools/badge_controller.py
BUTTONS = (
    (BUTTON_UP, "up"),
    (BUTTON_DOWN, "down"),
    (BUTTON_LEFT, "left"),
    (BUTTON_RIGHT, "right"),
    (BUTTON_SELECT, "select"),
    (BUTTON_BACK, "back"),
)

background = color.rgb(13, 17, 23)
white = color.rgb(230, 237, 243)
dim = color.rgb(139, 148, 158)
idle = color.rgb(33, 38, 45)
lit = color.rgb(57, 211, 83)

font = missing_details.mona_sans()
held = set()
presses = 0

# Where each button is drawn: (x, y, width, height)
PAD = {
    "up": (70, 78, 40, 40),
    "down": (70, 158, 40, 40),
    "left": (30, 118, 40, 40),
    "right": (110, 118, 40, 40),
    "select": (196, 98, 92, 40),
    "back": (196, 150, 92, 40),
}
LABELS = {"select": "Select", "back": "Back"}


def centered(text, top, size, pen):
    width, _ = screen.measure_text(text, font_size=size)
    screen.pen = pen
    screen.text(text, (WIDTH - width) / 2, top, size)


def send():
    """Prints one line per change since the last frame: +name pressed, -name let go."""
    global presses
    for button, name in BUTTONS:
        down = badge.held(button)
        if down and name not in held:
            held.add(name)
            presses += 1
            print("+" + name)
        elif not down and name in held:
            held.discard(name)
            print("-" + name)


def update():
    send()
    screen.pen = background
    screen.clear()
    screen.font = font
    centered("Controller", 12, 24, white)
    centered("plug in USB, run tools/badge_controller.py", 42, 12, dim)
    for name, (x, y, w, h) in PAD.items():
        screen.pen = lit if name in held else idle
        screen.shape(shape.rounded_rectangle(x, y, w, h, 6))
        label = LABELS.get(name)
        if label:
            screen.pen = background if name in held else white
            width, _ = screen.measure_text(label, font_size=14)
            screen.text(label, x + (w - width) / 2, y + 11, 14)
    centered(f"{presses} presses · Home to leave", 214, 12, dim)


run(update)
