"""Draws the share image and the 20-second promo video of Badge Studio.

Writes, in docs/media:
- og.png: 1200x630 preview shown when the site's link is shared.
- badge-studio.mp4: 1080x1080, 30 fps, 20 s (needs ffmpeg on the PATH).

The video uses the badge screenshots of docs/screenshots and two captures of
the site, passed as arguments: the landing page at 1280 px wide, full height,
and Badge Studio with an app's detail open. For example, with Chrome:
  chrome --headless=new --hide-scrollbars --window-size=1280,3400 --screenshot=landing.png https://akiyo974.github.io/badger/
  chrome --headless=new --hide-scrollbars --window-size=1280,1000 --screenshot=studio.png "https://akiyo974.github.io/badger/studio/#app=akiyo/radar"

Usage, from the repo root: py tools/make_promo.py landing.png studio.png
"""
import random
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SHOTS = "docs/screenshots"
OUT = "docs/media"
SIZE = 1080
FPS = 30
SECONDS = 20

BG = (13, 17, 23)
PANEL = (22, 27, 34)
LINE = (48, 54, 61)
TEXT = (230, 237, 243)
DIM = (139, 148, 158)
ACCENT = (211, 250, 55)
GREENS = ((14, 68, 41), (0, 109, 50), (38, 166, 65), (57, 211, 83))

FONTS = "C:/Windows/Fonts/"


def font(name, size):
    return ImageFont.truetype(FONTS + name, size)


BOLD = lambda size: font("segoeuib.ttf", size)  # noqa: E731
REGULAR = lambda size: font("segoeui.ttf", size)  # noqa: E731
MONO = lambda size: font("consolab.ttf", size)  # noqa: E731


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def shot(name):
    return Image.open(f"{SHOTS}/{name}").convert("RGB")


def badge_frame(screen, width):
    """The badge seen from the front: a dark bezel around the 4:3 screen."""
    height = width * 3 // 4
    border = width // 22
    frame = Image.new("RGBA", (width + 2 * border, height + 2 * border), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)
    draw.rounded_rectangle((0, 0, frame.width - 1, frame.height - 1), radius=border * 2, fill=(31, 38, 48))
    draw.rounded_rectangle((3, 3, frame.width - 4, frame.height - 4), radius=border * 2, outline=(58, 66, 78), width=2)
    frame.paste(screen.resize((width, height), Image.NEAREST), (border, border))
    return frame


def paste_shadowed(canvas, image, xy):
    shadow = Image.new("RGBA", (image.width + 80, image.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((40, 50, image.width + 40, image.height + 40), radius=40, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    canvas.alpha_composite(shadow, (xy[0] - 40, xy[1] - 40))
    canvas.alpha_composite(image if image.mode == "RGBA" else image.convert("RGBA"), xy)


def centered(draw, y, text, face, fill, width=SIZE):
    box = draw.textbbox((0, 0), text, font=face)
    draw.text(((width - (box[2] - box[0])) // 2 - box[0], y), text, font=face, fill=fill)


def with_alpha(color, alpha):
    return color + (int(255 * max(0.0, min(1.0, alpha))),)


random.seed(26)
GRID = [(c, r, random.random(), random.choice(GREENS)) for r in range(7) for c in range(18)]


def contribution_grid(canvas, t, top, alpha=1.0):
    """Squares lighting up like a contribution graph."""
    draw = ImageDraw.Draw(canvas)
    cell, gap = 46, 10
    left = (SIZE - (18 * cell + 17 * gap)) // 2
    for c, r, delay, colour in GRID:
        x, y = left + c * (cell + gap), top + r * (cell + gap)
        on = ease((t - delay * 1.6) / 0.35)
        base = (22, 27, 34)
        mix = tuple(int(b + (k - b) * on) for b, k in zip(base, colour))
        draw.rounded_rectangle((x, y, x + cell, y + cell), radius=8, fill=with_alpha(mix, alpha))


# ---------- scenes: each draws one frame at its own time t ----------

def scene_title(t):
    canvas = Image.new("RGBA", (SIZE, SIZE), BG + (255,))
    contribution_grid(canvas, t, 600)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    rise = int(30 * (1 - ease(t / 0.8)))
    centered(draw, 190 + rise, "Your GitHub Universe", BOLD(76), with_alpha(TEXT, t / 0.6))
    centered(draw, 285 + rise, "badge is hackable.", BOLD(76), with_alpha(ACCENT, (t - 0.4) / 0.6))
    centered(draw, 420, "Badger 2350 · RP2350 · MicroPython", REGULAR(36), with_alpha(DIM, (t - 1.0) / 0.6))
    canvas.alpha_composite(layer)
    return canvas


MENU = shot("menu.png")
DIZZY = shot("menu-dizzy.png")


def scene_badge(t):
    canvas = Image.new("RGBA", (SIZE, SIZE), BG + (255,))
    draw = ImageDraw.Draw(canvas)
    centered(draw, 90, "I built my own apps for it", BOLD(58), TEXT)
    centered(draw, 170, "and a custom home screen", REGULAR(40), DIM)
    screen = Image.blend(MENU, DIZZY, ease((t - 1.8) / 0.4))
    zoom = 0.96 + 0.04 * ease(t / 3.5)
    frame = badge_frame(screen, int(820 * zoom))
    paste_shadowed(canvas, frame, ((SIZE - frame.width) // 2, 300 + (680 - frame.height) // 2))
    if t > 2.0:
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        tag = ImageDraw.Draw(layer)
        tag.rounded_rectangle((330, 965, 750, 1025), radius=30, fill=with_alpha(GREENS[1], (t - 2.0) / 0.3))
        centered(tag, 972, "shake it: Mona gets dizzy", REGULAR(32), with_alpha(ACCENT, (t - 2.0) / 0.3))
        canvas.alpha_composite(layer)
    return canvas


def browser(page, width, height, scroll):
    """A browser window showing part of a page."""
    bar = 54
    window = Image.new("RGBA", (width, height + bar), PANEL + (255,))
    draw = ImageDraw.Draw(window)
    for i, colour in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        draw.ellipse((22 + i * 30, 19, 38 + i * 30, 35), fill=colour)
    draw.rounded_rectangle((130, 12, width - 30, 42), radius=15, fill=(13, 17, 23))
    draw.text((150, 14), "akiyo974.github.io/badger", font=MONO(20), fill=DIM)
    scale = width / page.width
    crop = page.crop((0, int(scroll), page.width, int(scroll + height / scale)))
    window.paste(crop.resize((width, height), Image.LANCZOS), (0, bar))
    mask = Image.new("L", window.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, window.width - 1, window.height - 1), radius=22, fill=255)
    window.putalpha(mask)
    return window


def scene_store(t, landing):
    canvas = Image.new("RGBA", (SIZE, SIZE), BG + (255,))
    draw = ImageDraw.Draw(canvas)
    centered(draw, 70, "Badge Studio", BOLD(78), ACCENT)
    centered(draw, 170, "an app store for the badge, in your browser", REGULAR(38), TEXT)
    # From the store's title down through the cards
    start, end = 980, landing.height - 1500
    scroll = start + (end - start) * ease((t - 0.6) / 3.6)
    paste_shadowed(canvas, browser(landing, 940, 720, scroll), (70, 270))
    return canvas


def scene_studio(t, studio):
    canvas = Image.new("RGBA", (SIZE, SIZE), BG + (255,))
    draw = ImageDraw.Draw(canvas)
    centered(draw, 70, "Plug in over USB. Click Install.", BOLD(54), TEXT)
    centered(draw, 150, "Web Serial · no install · checked writes", REGULAR(36), DIM)
    zoom = 1.0 + 0.08 * ease(t / 3.0)
    width = int(720 * zoom)
    page = studio.crop((270, 90, 1010, 610))
    window = browser(page, width, int(width * page.height / page.width), 0)
    paste_shadowed(canvas, window, ((SIZE - window.width) // 2, 225))
    if t > 1.2:
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        chips = ImageDraw.Draw(layer)
        a = (t - 1.2) / 0.3
        for i, label in enumerate(("App store", "Extensions + backups", "Home screen", "Screenshots")):
            y = 830 + (i // 2) * 90
            x = 120 + (i % 2) * 430
            chips.rounded_rectangle((x, y, x + 400, y + 66), radius=33, fill=with_alpha(PANEL, a), outline=with_alpha(LINE, a), width=2)
            box = chips.textbbox((0, 0), label, font=BOLD(30))
            chips.text((x + 200 - (box[2] - box[0]) // 2, y + 13), label, font=BOLD(30), fill=with_alpha(ACCENT if i == 0 else TEXT, a))
        canvas.alpha_composite(layer)
    return canvas


MONTAGE = (
    ("radar.png", "Radar", "badges met nearby"),
    ("duck-maze.png", "Duck Maze", "tilt to play"),
    ("badge-qr.png", "Badge", "QR codes + NFC card"),
    ("pedometer.png", "Pedometer", "steps from the watch"),
    ("contacts.png", "Contacts", "swap cards back to back"),
)
MONTAGE_SHOTS = [shot(name) for name, _, _ in MONTAGE]


def scene_montage(t):
    canvas = Image.new("RGBA", (SIZE, SIZE), BG + (255,))
    each = 0.9
    index = min(int(t / each), len(MONTAGE) - 1)
    local = t - index * each
    screen = MONTAGE_SHOTS[index]
    if local > each - 0.15 and index + 1 < len(MONTAGE):
        screen = Image.blend(screen, MONTAGE_SHOTS[index + 1], (local - (each - 0.15)) / 0.15)
    frame = badge_frame(screen, 820)
    paste_shadowed(canvas, frame, ((SIZE - frame.width) // 2, 140))
    draw = ImageDraw.Draw(canvas)
    _, name, line = MONTAGE[index]
    centered(draw, 830, name, BOLD(64), ACCENT)
    centered(draw, 920, line, REGULAR(40), TEXT)
    # Progress dots
    for i in range(len(MONTAGE)):
        x = SIZE // 2 - 70 + i * 35
        draw.ellipse((x, 1010, x + 14, 1024), fill=ACCENT if i == index else LINE)
    return canvas


def scene_end(t):
    canvas = Image.new("RGBA", (SIZE, SIZE), BG + (255,))
    contribution_grid(canvas, t + 2.5, 760, alpha=0.5)
    draw = ImageDraw.Draw(canvas)
    # The site's mark: four squares, the last one round
    left, top, cell = SIZE // 2 - 70, 140, 64
    draw.rounded_rectangle((left, top, left + cell, top + cell), radius=10, fill=GREENS[3])
    draw.rounded_rectangle((left + cell + 12, top, left + 2 * cell + 12, top + cell), radius=10, fill=GREENS[1])
    draw.rounded_rectangle((left, top + cell + 12, left + cell, top + 2 * cell + 12), radius=10, fill=GREENS[2])
    draw.ellipse((left + cell + 12, top + cell + 12, left + 2 * cell + 12, top + 2 * cell + 12), fill=ACCENT)
    centered(draw, 320, "Badge Studio", BOLD(92), TEXT)
    centered(draw, 440, "Plug in · Connect · Install", REGULAR(44), DIM)
    draw.rounded_rectangle((170, 540, 910, 620), radius=40, fill=ACCENT)
    centered(draw, 552, "akiyo974.github.io/badger", MONO(42), BG)
    centered(draw, 665, "#GitHubUniverse", BOLD(40), GREENS[3])
    return canvas


def timeline(landing, studio):
    return (
        (2.6, scene_title),
        (3.4, scene_badge),
        (3.8, lambda t: scene_store(t, landing)),
        (2.8, lambda t: scene_studio(t, studio)),
        (4.5, scene_montage),
        (2.9, scene_end),
    )


def frame_at(scenes, t):
    fade = 0.35
    start = 0.0
    for index, (length, draw) in enumerate(scenes):
        end = start + length
        last = index == len(scenes) - 1
        if t < end or last:
            image = draw(t - start)
            # Cross-fade into the next scene at the end of this one
            if not last and t > end - fade:
                following = scenes[index + 1][1](0.0)
                image = Image.blend(image, following, (t - (end - fade)) / fade)
            if t < 0.4:
                image = Image.blend(Image.new("RGBA", image.size, BG + (255,)), image, t / 0.4)
            return image.convert("RGB")
        start = end
    raise ValueError(t)


def og_image():
    canvas = Image.new("RGBA", (1200, 630), BG + (255,))
    draw = ImageDraw.Draw(canvas)
    for i, colour in enumerate(GREENS):
        draw.rounded_rectangle((70 + i * 40, 80, 100 + i * 40, 110), radius=6, fill=colour)
    draw.text((70, 140), "Badge Studio", font=BOLD(76), fill=ACCENT)
    draw.text((70, 245), "Hack your GitHub", font=BOLD(50), fill=TEXT)
    draw.text((70, 305), "Universe badge from", font=BOLD(50), fill=TEXT)
    draw.text((70, 365), "the browser.", font=BOLD(50), fill=TEXT)
    draw.text((70, 455), "App store · extensions · home screen", font=REGULAR(28), fill=DIM)
    draw.text((70, 530), "akiyo974.github.io/badger", font=MONO(28), fill=ACCENT)
    frame = badge_frame(MENU, 480)
    paste_shadowed(canvas, frame, (1200 - frame.width - 60, (630 - frame.height) // 2))
    canvas.convert("RGB").save(f"{OUT}/og.png")


def video(landing_path, studio_path):
    landing = Image.open(landing_path).convert("RGB")
    studio = Image.open(studio_path).convert("RGB")
    scenes = timeline(landing, studio)
    encoder = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{SIZE}x{SIZE}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", f"{OUT}/badge-studio.mp4"],
        stdin=subprocess.PIPE,
    )
    for n in range(FPS * SECONDS):
        encoder.stdin.write(frame_at(scenes, n / FPS).tobytes())
    encoder.stdin.close()
    if encoder.wait():
        raise SystemExit("ffmpeg failed")


if __name__ == "__main__":
    og_image()
    print("wrote", f"{OUT}/og.png")
    if len(sys.argv) == 3:
        video(sys.argv[1], sys.argv[2])
        print("wrote", f"{OUT}/badge-studio.mp4")
