import os
import struct
from array import array

APP_DIR = "/system/startup"

os.chdir(APP_DIR)

DATA_FILE = "animation.bin"
MAGIC = b"BWAN"
VERSION = 1
FINAL = color.rgb(255, 255, 255)


def load(path):
    with open(path, "rb") as file:
        data = file.read()
    magic, version, fps, width, height, shape_count, colour_count, frame_count = struct.unpack_from("<4sHfHHHHH", data, 0)
    if magic != MAGIC:
        raise ValueError("not a baked animation")
    if version != VERSION:
        raise ValueError("unsupported animation version %d" % version)
    offset = struct.calcsize("<4sHfHHHHH")
    shapes = []
    for _ in range(shape_count):
        rule, contour_count = struct.unpack_from("<BB", data, offset)
        offset += 2
        contours = []
        for _ in range(contour_count):
            (points,) = struct.unpack_from("<H", data, offset)
            offset += 2
            contours.append(array("f", struct.unpack_from("<%df" % (points * 2), data, offset)))
            offset += points * 8
        shapes.append((image.EVEN_ODD if rule == 2 else image.NON_ZERO, shape.custom(*contours)))
    colours = []
    for _ in range(colour_count):
        r, g, b, a = struct.unpack_from("<4B", data, offset)
        offset += 4
        colours.append(color.rgb(r, g, b, a))
    frames = []
    record_size = struct.calcsize("<HH5f")
    for _ in range(frame_count):
        (count,) = struct.unpack_from("<H", data, offset)
        offset += 2
        records = []
        for _ in range(count):
            records.append(struct.unpack_from("<HH5f", data, offset))
            offset += record_size
        frames.append(records)
    return fps, shapes, colours, frames


previous_clear = badge.default_clear

badge.mode(HIRES | VSYNC)
badge.default_clear = None
screen.antialias = image.X4

fps, shapes, colours, frames = load(DATA_FILE)
started = None
finished = False


def draw(records):
    for shape_id, colour_id, tx, ty, angle, sx, sy in records:
        rule, outline = shapes[shape_id]
        transform = mat3().translate(vec2(tx, ty))
        if angle:
            transform.rotate(angle)
        outline.transform = transform.scale(sx, sy)
        screen.fill_rule = rule
        screen.pen = colours[colour_id]
        screen.shape(outline)


def update():
    global started, finished
    if finished:
        return True
    if started is None:
        started = badge.ticks
    frame = (badge.ticks - started) * fps // 1000
    if badge.buttons.pressed() or frame >= len(frames):
        screen.pen = FINAL
        screen.clear()
        finished = True
        return None
    draw(frames[int(frame)])
    return None


def on_exit():
    screen.antialias = image.OFF
    screen.fill_rule = image.NON_ZERO
    badge.default_clear = previous_clear


run(update)
