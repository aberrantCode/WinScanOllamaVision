"""One-time: generate assets/icon.ico from assets/icon.png.

Run manually when icon.png changes. The .ico is committed; it is not
regenerated at build time.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

SRC = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
DST = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    img = Image.open(SRC).convert("RGBA")
    img.save(DST, format="ICO", sizes=SIZES)
    print(f"Wrote {DST} ({DST.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
