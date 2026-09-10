#!/usr/bin/env python3
"""
mesh_batch.py — check and render every mesh in a directory, then rank them.

    python tools/mesh_batch.py outputs/round2
    python tools/mesh_batch.py outputs/round2 --height 160 --ext glb stl

Writes <name>_views.png beside each mesh and <dir>/mesh_report.md with one
row per mesh — triangles, watertight, height, % needing support, the band
where the support is — sorted so the most printable candidate is on top.
Stage 2 produces a pile of these; this is how you pick one without opening
each in a viewer.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_mesh as cm  # noqa: E402
import mesh_views  # noqa: E402


def band_text(band):
    if not band:
        return "none"
    z0, z1, area, worst = band
    return f"z {z0:.0f}-{z1:.0f} mm ({area:.0f} mm², worst {worst:.0f}°)"


def report_rows(results):
    yield "| file | tris | watertight | height | needs support | worst band | views |"
    yield "|---|---:|:---:|---:|---:|---|---|"
    for name, info, png, err in results:
        if err:
            yield f"| `{name}` | — | — | — | — | failed: {err} | — |"
            continue
        yield (f"| `{name}` | {info['faces']:,} | {'yes' if info['watertight'] else '**no**'} "
               f"| {info['height']:.1f} mm | {info['unsupported_pct']:.1f}% "
               f"| {band_text(info['worst_band'])} | [{png.name}]({png.name}) |")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir")
    ap.add_argument("--height", type=float, default=160.0,
                    help="scale every mesh to this height in mm before measuring (default 160)")
    ap.add_argument("--ext", nargs="+", default=["glb"],
                    help="extensions to include (default: glb)")
    ap.add_argument("--up", choices=cm.UP_CHOICES, default="auto")
    ap.add_argument("--limit", type=float, default=cm.LIMIT_DEG)
    args = ap.parse_args()

    root = Path(args.dir)
    files = sorted(p for p in root.iterdir()
                   if p.suffix.lower().lstrip(".") in {e.lower().lstrip(".") for e in args.ext})
    if not files:
        raise SystemExit(f"no {'/'.join(args.ext)} files in {root}")

    results = []
    for path in files:
        t0 = time.time()
        try:
            png, info, up = mesh_views.render(path, height=args.height, up=args.up,
                                              limit=args.limit)
            results.append((path.name, info, png, None))
            print(f"{path.name:<40} {info['faces']:>9,} tris  watertight "
                  f"{'yes' if info['watertight'] else 'no ':<3}  support "
                  f"{info['unsupported_pct']:5.1f}%   ({time.time() - t0:.1f} s)")
        except Exception as e:  # one bad file shouldn't sink the batch
            results.append((path.name, None, None, f"{type(e).__name__}: {e}"))
            print(f"{path.name:<40} FAILED {type(e).__name__}: {e}")

    # printable first: closed meshes, then least support
    results.sort(key=lambda r: (r[3] is not None,
                                not (r[1] and r[1]["watertight"]),
                                r[1]["unsupported_pct"] if r[1] else 1e9))

    report = root / "mesh_report.md"
    lines = [f"# Mesh report — `{root}`", "",
             f"{len(files)} meshes, scaled to {args.height:g} mm, overhang limit "
             f"{args.limit:g}°. Sorted: watertight first, then least support. "
             f"`watertight: no` means run `tools/mesh_repair.py` before trusting the "
             f"support number.", ""]
    lines += list(report_rows(results))
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
