#!/usr/bin/env python3
"""
Turn a photo into the ASCII portrait the card expects.

    pip install pillow
    python tools/photo_to_ascii.py me.jpg

That writes assets/portrait.txt at exactly the size config.py asks for and
prints a preview. Then:

    python today.py --demo

Options worth knowing
---------------------
    --invert        dark characters on a light background. Use this only if
                    you are optimising for the light theme; the default suits
                    dark, which is what most people see.
    --ramp blocks   ' .:-=+*#%@' is the default. 'blocks' uses shading blocks,
                    which look denser and hide less detail.
    --contrast 1.4  push contrast before sampling. Faces almost always want
                    more than the photo has.
    --sharpen       unsharp mask first. At 44x32 every edge counts.
    --no-crop       skip the automatic aspect crop and squash the whole frame.
    --gravity top   which part of the photo to keep when cropping. Portraits
                    usually want 'top' or 'center'.

Getting a good result
---------------------
The grid is tiny, so composition does more work than any flag. Crop tight to
head and shoulders before you start, use an image with a plain background and
strong side lighting, and expect to run this three or four times.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import themes  # noqa: E402
import render  # noqa: E402

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError:
    sys.exit("Pillow is required:  pip install pillow")


RAMPS = {
    "classic": " .:-=+*#%@",
    "fine": " .'`^\",:;Il!i><~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "blocks": " .:-=+*#%@█",
    "shade": " ░▒▓█",
}


def target_aspect() -> float:
    """
    Width / height of the portrait as it is actually drawn, in pixels.

    A character cell is not square: it is ASCII_FONT * CELL_RATIO wide and
    ASCII_DY tall. Crop the photo to this and nothing gets stretched.
    """
    cell_w = themes.ASCII_FONT * render.CELL_RATIO
    cell_h = themes.ASCII_DY
    return (config.ASCII_COLS * cell_w) / (config.ASCII_ROWS * cell_h)


def crop_to_aspect(image, aspect: float, gravity: str):
    w, h = image.size
    if w / h > aspect:            # too wide - trim the sides
        new_w = int(round(h * aspect))
        left = (w - new_w) // 2
        box = (left, 0, left + new_w, h)
    else:                          # too tall - trim top/bottom
        new_h = int(round(w / aspect))
        if gravity == "top":
            top = 0
        elif gravity == "bottom":
            top = h - new_h
        else:
            top = (h - new_h) // 2
        box = (0, top, w, top + new_h)
    return image.crop(box)


def to_ascii(image, ramp: str, invert: bool) -> list[str]:
    cols, rows = config.ASCII_COLS, config.ASCII_ROWS
    small = image.resize((cols, rows), Image.LANCZOS)
    pixels = small.load()

    steps = len(ramp) - 1
    out = []
    for y in range(rows):
        line = []
        for x in range(cols):
            value = pixels[x, y] / 255.0
            if invert:
                value = 1.0 - value
            line.append(ramp[int(round(value * steps))])
        # Trailing spaces are meaningless in the SVG, but they make the file
        # noisy in diffs.
        out.append("".join(line).rstrip().ljust(cols))
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("image", help="path to a photo")
    parser.add_argument("-o", "--out", default=config.ASCII_ART_FILE)
    parser.add_argument("--ramp", default="classic", choices=sorted(RAMPS))
    parser.add_argument("--invert", action="store_true")
    parser.add_argument("--contrast", type=float, default=1.25)
    parser.add_argument("--brightness", type=float, default=1.0)
    parser.add_argument("--sharpen", action="store_true")
    parser.add_argument("--no-crop", action="store_true")
    parser.add_argument(
        "--gravity", default="center", choices=("top", "center", "bottom")
    )
    parser.add_argument("--stdout", action="store_true", help="print, do not write")
    args = parser.parse_args(argv)

    image = Image.open(args.image)
    if image.mode in ("RGBA", "LA", "P"):
        # Flatten transparency onto black, matching the dark card.
        image = image.convert("RGBA")
        flat = Image.new("RGBA", image.size, (0, 0, 0, 255))
        image = Image.alpha_composite(flat, image)
    image = image.convert("L")

    if not args.no_crop:
        image = crop_to_aspect(image, target_aspect(), args.gravity)

    image = ImageOps.autocontrast(image, cutoff=1)
    if args.sharpen:
        image = image.filter(
            ImageFilter.UnsharpMask(radius=2, percent=140, threshold=2)
        )
    if args.contrast != 1.0:
        image = ImageEnhance.Contrast(image).enhance(args.contrast)
    if args.brightness != 1.0:
        image = ImageEnhance.Brightness(image).enhance(args.brightness)

    rows = to_ascii(image, RAMPS[args.ramp], args.invert)

    border = "+" + "-" * config.ASCII_COLS + "+"
    print(border)
    for line in rows:
        print("|" + line + "|")
    print(border)
    print(f"{config.ASCII_COLS} x {config.ASCII_ROWS}")

    if args.stdout:
        return 0

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(rows) + "\n")
    print(f"\nwrote {args.out}\nnow run:  python today.py --demo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
