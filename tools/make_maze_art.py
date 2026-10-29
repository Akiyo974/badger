"""Draws the pixel art of the Duck Maze app, in the palette of Mona's sprites.

Writes, in system/apps/duck_maze:
- duck.png: 3 frames of 12x10, the rubber duck to collect, bobbing.
- icon.png: 24x24 menu icon, a marble in a corner of the maze next to a duck.

Usage, from the repo root: py tools/make_maze_art.py
"""
from PIL import Image

OUT_DIR = "system/apps/duck_maze"

COLOURS = {
    "Y": (255, 211, 61, 255),   # Mona's sparkle yellow
    "y": (222, 158, 30, 255),
    "O": (255, 128, 40, 255),
    "K": (5, 38, 76, 255),      # Mona's navy
    "W": (255, 248, 242, 255),  # Mona's face white
}

DUCK = (
    "......YYY...",
    ".....YYYYY..",
    ".....YYKYYOO",
    ".....YWYYYOO",
    "......YYYY..",
    "Y...YYYYYYY.",
    "YYYYYYYYYYY.",
    "YYYyyyyYYYY.",
    ".YYYYYYYYYY.",
    "..YYYYYYYY..",
)

# Background, contribution-graph greens for the walls, marble greys
ICON_COLOURS = {
    ".": (13, 17, 23),
    "1": (14, 68, 41),
    "2": (0, 109, 50),
    "3": (38, 166, 65),
    "4": (57, 211, 83),
    "m": (150, 170, 190),
    "M": (215, 228, 240),
    "h": (255, 255, 255),
    "Y": (255, 211, 61),
    "y": (222, 158, 30),
    "O": (255, 128, 40),
    "K": (5, 38, 76),
}

ICON = (
    "444.333.222.111.444.333.",
    "444.333.222.111.444.333.",
    "444.333.222.111.444.333.",
    "........................",
    "333.....................",
    "333............YYY......",
    "333...........YYYYY.....",
    "...........mm.YYKYYOO...",
    "222.......mMMmYYYYYO....",
    "222......mMhMMmYYYY.....",
    "222......mMMMMmYYYYYYY..",
    ".........mMMMMmYYyyyYY..",
    "111.......mMMm.YYYYYY...",
    "111........mm...YYYY....",
    "111.....................",
    "........................",
    "444.........333.222.111.",
    "444.........333.222.111.",
    "444.........333.222.111.",
    "........................",
    "333.222.111.444.333.222.",
    "333.222.111.444.333.222.",
    "333.222.111.444.333.222.",
    "........................",
)


def duck_frames():
    width, height = len(DUCK[0]), len(DUCK)
    sheet = Image.new("RGBA", (width * 3, height + 2), (0, 0, 0, 0))
    # A gentle bob: up, middle, down
    for index, lift in enumerate((0, 1, 2)):
        for y, row in enumerate(DUCK):
            for x, cell in enumerate(row):
                if cell in COLOURS:
                    sheet.putpixel((index * width + x, y + lift), COLOURS[cell])
    sheet.save(f"{OUT_DIR}/duck.png")


def icon():
    image = Image.new("RGB", (24, 24))
    for y, row in enumerate(ICON):
        for x, cell in enumerate(row):
            image.putpixel((x, y), ICON_COLOURS[cell])
    image.save(f"{OUT_DIR}/icon.png")


if __name__ == "__main__":
    duck_frames()
    icon()
    print("wrote duck.png and icon.png in", OUT_DIR)
