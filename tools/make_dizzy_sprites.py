"""Draws the sprites of the dizzy Mona animation shown when the badge is shaken.

Writes, in system/apps/menu:
- mona-dizzy.png: 4 frames of 28x24, Mona with X eyes and a wobbly mouth, her
  head swaying. Made from Mona Pet's mona-default.png, same palette.
- duck.png: 4 frames of 12x10, a rubber duck flapping (2 frames facing right,
  then the same 2 facing left) that circles Mona's head.

Usage, from the repo root: py tools/make_dizzy_sprites.py
"""
from PIL import Image

SOURCE = "system/apps/mona_pet/assets/mona-sprites/mona-default.png"
OUT_DIR = "system/apps/menu"
FRAME_W, FRAME_H = 28, 24
SOURCE_FRAME = 1  # Mona looking straight ahead

TRANSPARENT, BLUE, FACE, NAVY, SPARKLE = 0, 1, 2, 3, 7

# X eyes drawn over the round ones; each eye is 1x2 pixels at x 10 and 16
EYES = ((10, 11), (16, 11))
X_PIXELS = ((-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1))
# Open "o" mouth replaced by a little zigzag
OLD_MOUTH = ((12, 12), (13, 12), (12, 13), (13, 13))
NEW_MOUTH = ((11, 14), (12, 13), (13, 14), (14, 13), (15, 14))
SWAY = (0, 1, 0, -1)


def dizzy_mona():
    source = Image.open(SOURCE)
    frame = source.crop((SOURCE_FRAME * FRAME_W, 0, (SOURCE_FRAME + 1) * FRAME_W, FRAME_H))
    pixels = frame.load()

    for x in range(FRAME_W):
        for y in range(FRAME_H):
            if pixels[x, y] == SPARKLE:
                pixels[x, y] = TRANSPARENT
    for x, y in EYES:
        pixels[x, y] = pixels[x, y + 1] = FACE
        for dx, dy in X_PIXELS:
            pixels[x + dx, y + 1 + dy] = NAVY
    for x, y in OLD_MOUTH:
        pixels[x, y] = FACE
    for x, y in NEW_MOUTH:
        pixels[x, y] = NAVY

    sheet = Image.new("P", (FRAME_W * len(SWAY), FRAME_H), TRANSPARENT)
    sheet.putpalette(source.getpalette())
    for index, shift in enumerate(SWAY):
        sheet.paste(frame, (index * FRAME_W + shift, 0))
    sheet.save(f"{OUT_DIR}/mona-dizzy.png", transparency=source.info["transparency"])


YELLOW = (255, 211, 61, 255)
SHADE = (222, 158, 30, 255)
BEAK = (255, 128, 40, 255)
EYE = (5, 38, 76, 255)
COLOURS = {"Y": YELLOW, "y": SHADE, "O": BEAK, "K": EYE}

DUCK_WING_DOWN = (
    "......YYY...",
    ".....YYYYY..",
    ".....YYKYYOO",
    ".....YYYYYOO",
    "......YYYY..",
    "Y...YYYYYYY.",
    "YYYYYYYYYYY.",
    "YYYyyyyYYYY.",
    ".YYYYYYYYYY.",
    "..YYYYYYYY..",
)
DUCK_WING_UP = (
    "......YYY...",
    ".....YYYYY..",
    ".....YYKYYOO",
    ".....YYYYYOO",
    "......YYYY..",
    "Y..yyYYYYYY.",
    "YYYYyyyYYYY.",
    "YYYYYYYYYYY.",
    ".YYYYYYYYYY.",
    "..YYYYYYYY..",
)


def duck_frame(rows):
    frame = Image.new("RGBA", (len(rows[0]), len(rows)), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if cell in COLOURS:
                frame.putpixel((x, y), COLOURS[cell])
    return frame


def ducks():
    right = [duck_frame(DUCK_WING_DOWN), duck_frame(DUCK_WING_UP)]
    left = [frame.transpose(Image.FLIP_LEFT_RIGHT) for frame in right]
    frames = right + left
    width, height = frames[0].size
    sheet = Image.new("RGBA", (width * len(frames), height), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sheet.paste(frame, (index * width, 0))
    sheet.save(f"{OUT_DIR}/duck.png")


if __name__ == "__main__":
    dizzy_mona()
    ducks()
    print("wrote mona-dizzy.png and duck.png in", OUT_DIR)
