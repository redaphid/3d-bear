"""Build docs/ for GitHub Pages: optimise the curated images into docs/img/
and copy the print-ready STLs into docs/print/.

Re-runnable. Prints a size total at the end. Keeps docs/ well under 40 MB.

    python tools/build_site.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
IMG = DOCS / "img"
PRINT = DOCS / "print"

SHEET_MAX = 1800    # long side for contact sheets / six-view plates / ladders
SINGLE_MAX = 1200   # long side for single renders
CUTOUT_MAX = 900    # long side for the transparent cutouts (palette PNG)
JPEG_Q = 85

R1 = ROOT / "outputs/round1"
R2 = ROOT / "outputs/stage1_refs/round2"
R2Z = ROOT / "outputs/stage1_refs/round2z"
MESH = ROOT / "outputs/stage2_mesh/round2z"
PARAMS = ROOT / "outputs/stage2_params/d"
SCRATCH = ROOT / "outputs/scratch"
P1 = ROOT / "outputs/stage3_print/round1_d"
PRINT_READY = ROOT / "print-ready"

IDS = "abcdefghijklmnopqrst"

# (source, destination name, kind)  kind: photo | sheet | cutout | hero
CURATED: list[tuple[Path, str, str]] = [
    # cover: full-quality cutout of the recommended bear, and the one Qwen three-quarter
    (MESH / "c_cutout.png", "hero-c-cutout.png", "hero"),
    (R2 / "d.png", "qwen-d.jpg", "photo"),
    # stage 1: the frontal round, all twenty references, the sheet
    *[(R1 / f"ref_{i}.png", f"round1-{i}.jpg", "photo") for i in "abcd"],
    *[(R2Z / f"{i}.png", f"ref-{i}.jpg", "photo") for i in IDS],
    (R2Z / "sheet.png", "round2z-sheet.jpg", "sheet"),
    # stage 2: first mesh, the wall, the whole parameter sweep, all twenty reconstructions + cutouts
    (SCRATCH / "mesh_round1_d_views.png", "mesh-round1-d-views.jpg", "sheet"),
    (PARAMS / "nobg_o384_s30_views.png", "nobg-wall-views.jpg", "sheet"),
    (PARAMS / "o256_s30_views.png", "sweep-o256.jpg", "sheet"),
    (PARAMS / "o384_s30_views.png", "sweep-o384.jpg", "sheet"),
    (PARAMS / "o384_s30_t05_views.png", "sweep-t05.jpg", "sheet"),
    (PARAMS / "o384_s30_t07_views.png", "sweep-t07.jpg", "sheet"),
    (PARAMS / "o384_s30_seed2_views.png", "sweep-seed2.jpg", "sheet"),
    (PARAMS / "o384_s30_seed3_views.png", "sweep-seed3.jpg", "sheet"),
    (PARAMS / "o384_s50_views.png", "sweep-s50.jpg", "sheet"),
    *[(MESH / f"{i}_views.png", f"mesh-{i}.jpg", "sheet") for i in IDS],
    *[(MESH / f"{i}_cutout.png", f"cut-{i}.png", "cutout") for i in IDS],
    # stage 3: repair, face ladder, the print-ready previews
    (P1 / "round1_d_print_views.png", "print-round1-d.jpg", "sheet"),
    (P1 / "round1_d_faces_ladder.png", "faces-ladder.jpg", "sheet"),
    *[(PRINT_READY / f"preview-bear-{i}.png", f"print-{i}.jpg", "sheet") for i in "cokmd"],
]

STLS = sorted(PRINT_READY.glob("*.stl")) + [PRINT_READY / "README.md"]


def fit(im: Image.Image, long_side: int) -> Image.Image:
    w, h = im.size
    scale = long_side / max(w, h)
    if scale >= 1:
        return im
    return im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)


def flatten(im: Image.Image) -> Image.Image:
    """Composite RGBA plates onto their own corner colour (the off-white
    matplotlib ground), so the JPEG has no black fringe."""
    if im.mode in ("RGBA", "LA"):
        rgba = im.convert("RGBA")
        bg = Image.new("RGB", im.size, rgba.getpixel((0, 0))[:3])
        bg.paste(rgba, mask=rgba.split()[3])
        return bg
    return im.convert("RGB")


def build_image(src: Path, name: str, kind: str) -> int:
    dst = IMG / name
    with Image.open(src) as im:
        if kind == "hero":
            fit(im.convert("RGBA"), SINGLE_MAX).save(dst, "PNG", optimize=True)
        elif kind == "cutout":
            # grey clay quantises losslessly to 256 colours; alpha survives as a palette entry
            out = fit(im.convert("RGBA"), CUTOUT_MAX).quantize(colors=256, method=Image.Quantize.FASTOCTREE)
            out.save(dst, "PNG", optimize=True)
        else:
            out = fit(flatten(im), SHEET_MAX if kind == "sheet" else SINGLE_MAX)
            out.save(dst, "JPEG", quality=JPEG_Q, optimize=True, progressive=True)
    return dst.stat().st_size


def main() -> int:
    IMG.mkdir(parents=True, exist_ok=True)
    PRINT.mkdir(parents=True, exist_ok=True)
    missing = [s for s, _, _ in CURATED if not s.exists()] + [s for s in STLS if not s.exists()]
    if missing:
        for m in missing:
            print(f"missing: {m}", file=sys.stderr)
        return 1

    # drop stale images from earlier inventories
    keep = {name for _, name, _ in CURATED}
    for old in IMG.glob("*"):
        if old.name not in keep:
            old.unlink()

    total = 0
    for src, name, kind in CURATED:
        size = build_image(src, name, kind)
        total += size
        print(f"{name:28s} {size/1024:7.0f} KB")

    for src in STLS:
        dst = PRINT / src.name
        shutil.copy2(src, dst)
        size = dst.stat().st_size
        total += size
        print(f"print/{src.name:50s} {size/1024:7.0f} KB")

    index = DOCS / "index.html"
    if index.exists():
        total += index.stat().st_size
    print(f"\ndocs/ total: {total/1024/1024:.1f} MB  ({len(CURATED)} images, {len(STLS)} print files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
