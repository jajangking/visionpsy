#!/data/data/com.termux/files/usr/bin/env python3
import sys
from PIL import Image

src, dst, maxpx, quality = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
im = Image.open(src).convert("RGB")
w, h = im.size
scale = min(1.0, maxpx / max(w, h))
if scale < 1.0:
    im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
im.save(dst, "JPEG", quality=quality)