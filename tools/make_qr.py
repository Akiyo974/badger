import sys

import qrcode
from PIL import Image

SIZE = 180
BORDER = 2
TARGETS = {
    "qr_site.png": "https://christendijoux.com/",
    "qr_linkedin.png": "https://www.linkedin.com/in/christen-dijoux",
    "qr_github.png": "https://github.com/Akiyo974",
}

out_dir = sys.argv[1]

for name, url in TARGETS.items():
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=BORDER, box_size=1)
    qr.add_data(url)
    qr.make(fit=True)
    small = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    # Agrandissement en pixels entiers pour garder des modules nets
    scale = SIZE // small.width
    sharp = small.resize((small.width * scale, small.height * scale), Image.NEAREST)
    canvas = Image.new("RGB", (SIZE, SIZE), "white")
    offset = (SIZE - sharp.width) // 2
    canvas.paste(sharp, (offset, offset))
    canvas.save(f"{out_dir}/{name}", optimize=True)
    print(name, f"{small.width} modules x{scale} -> {sharp.width}px")
