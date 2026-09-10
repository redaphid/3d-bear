#!/usr/bin/env python
"""Contact sheet for a sweep of candidate images.

    python tools/sheet.py outputs/round2 --items outputs/round2/items.json \
        --cols 5 --out outputs/round2/sheet.png

Lays out <dir>/<id>.png thumbnails in a grid (item order from items.json,
falling back to sorted filenames) with a label strip under each tile:
    <id>  <tag>  seed <seed>
Also writes a half-size <stem>_small.<ext> beside --out.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeuib.ttf",  # Segoe UI Bold
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/consolab.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def load_font(size):
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path, help="directory holding <id>.png files")
    ap.add_argument("--items", type=Path, help="items.json: {id: {tag, seed, ...}}")
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--thumb", type=int, default=380, help="tile width/height in px")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ext", default="png")
    args = ap.parse_args()

    items = {}
    if args.items:
        items = json.loads(args.items.read_text(encoding="utf-8"))
    ids = list(items) if items else sorted(p.stem for p in args.dir.glob(f"*.{args.ext}"))
    if not ids:
        sys.exit(f"no images found in {args.dir}")

    thumb = args.thumb
    pad = 14
    font_id = load_font(int(thumb * 0.095))    # ~36px at 380
    font_lbl = load_font(int(thumb * 0.068))   # ~26px at 380
    strip_h = int(thumb * 0.20)                # label strip under each tile
    tile_w, tile_h = thumb, thumb + strip_h
    cols = max(1, args.cols)
    rows = (len(ids) + cols - 1) // cols
    W = pad + cols * (tile_w + pad)
    H = pad + rows * (tile_h + pad)

    bg, strip_bg, fg_id, fg_lbl, missing_bg = (32, 32, 34), (18, 18, 20), (255, 210, 80), (235, 235, 235), (70, 30, 30)
    sheet = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(sheet)

    for n, iid in enumerate(ids):
        r, c = divmod(n, cols)
        x0 = pad + c * (tile_w + pad)
        y0 = pad + r * (tile_h + pad)
        src = args.dir / f"{iid}.{args.ext}"
        if src.exists():
            im = Image.open(src).convert("RGB")
            im.thumbnail((thumb, thumb), Image.LANCZOS)
            ox = x0 + (thumb - im.width) // 2
            oy = y0 + (thumb - im.height) // 2
            sheet.paste(im, (ox, oy))
        else:
            draw.rectangle([x0, y0, x0 + thumb, y0 + thumb], fill=missing_bg)
            draw.text((x0 + 16, y0 + thumb // 2 - 12), "MISSING", font=font_lbl, fill=fg_lbl)

        # label strip
        sy = y0 + thumb
        draw.rectangle([x0, sy, x0 + tile_w, sy + strip_h], fill=strip_bg)
        meta = items.get(iid, {})
        tag = str(meta.get("tag", ""))
        seed = meta.get("seed")
        draw.text((x0 + 12, sy + int(strip_h * 0.14)), iid, font=font_id, fill=fg_id)
        idw = draw.textlength(iid, font=font_id)
        label = tag + (f"   seed {seed}" if seed is not None else "")
        # shrink label font if it would overflow the tile
        f = font_lbl
        while draw.textlength(label, font=f) > tile_w - idw - 30 and f.size > 12:
            f = load_font(f.size - 2)
        draw.text((x0 + 12 + idw + 14, sy + int(strip_h * 0.30)), label, font=f, fill=fg_lbl)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    small = args.out.with_name(args.out.stem + "_small" + args.out.suffix)
    sheet.resize((W // 2, H // 2), Image.LANCZOS).save(small)
    print(f"wrote {args.out} ({W}x{H}) and {small} ({W//2}x{H//2}); {len(ids)} tiles, "
          f"{sum((args.dir / f'{i}.{args.ext}').exists() for i in ids)} present")


if __name__ == "__main__":
    main()
