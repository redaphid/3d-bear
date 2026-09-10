#!/usr/bin/env python
"""Write <dir>/index.md: one row per GLB with the numbers we pick on.

    python tools/mesh_index.py outputs/stage2_mesh/round2z [--height 160]

Runs check_mesh.py (--up auto) on every *.glb in the dir and tabulates file,
tris, watertight, height, footprint, % of surface needing support, plus links
to the rembg cutout (<stem>_cutout.png) and the six-view render
(<stem>_views.png, from tools/mesh_batch.py) when they sit beside the mesh.
Meshes that fail to load get a row saying so instead of killing the run.
"""
from __future__ import annotations
import argparse, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "check_mesh.py"

def check(glb: Path, height: float) -> dict:
    p = subprocess.run([sys.executable, str(CHECK), str(glb), "--up", "auto", "--height", str(height)],
                       capture_output=True, text=True)
    out = p.stdout + p.stderr
    def grab(pat, default="?"):
        m = re.search(pat, out); return m.group(1).strip() if m else default
    return {
        "tris": grab(r"triangles\s+([\d,]+)"),
        "watertight": grab(r"watertight\s+(True|False)"),
        "height": grab(r"height\s+([\d.]+ mm)"),
        "footprint": grab(r"footprint\s+([\d.]+ x [\d.]+ mm)"),
        "support": grab(r"needs support\s+([\d.]+%)"),
        "ok": "triangles" in out,  # check_mesh exits 1 for non-watertight; that is data, not failure
        "err": (out.strip().splitlines() or ["no output"])[-1],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir"); ap.add_argument("--height", type=float, default=160)
    a = ap.parse_args(); d = Path(a.dir)
    rows = []
    for glb in sorted(d.glob("*.glb")):
        r = check(glb, a.height); stem = glb.stem
        cut = f"[cutout]({stem}_cutout.png)" if (d / f"{stem}_cutout.png").exists() else ""
        views = f"[views]({stem}_views.png)" if (d / f"{stem}_views.png").exists() else ""
        if r["ok"]:
            wt = "yes" if r["watertight"] == "True" else "**no**"
            rows.append(f"| `{glb.name}` | {r['tris']} | {wt} | {r['height']} | {r['footprint']} | {r['support']} | {cut} {views} |")
        else:
            rows.append(f"| `{glb.name}` | FAILED: {r['err']} | | | | | {cut} |")
        print(glb.name, r["tris"], "wt", r["watertight"], r["footprint"], r["support"])
    md = [f"# {d.as_posix()} — mesh index", "",
          f"Hunyuan3D 2.1 output, scaled to {a.height:g} mm tall (GLB is Y-up; oriented with `--up auto`). "
          "`watertight: no` means run `tools/mesh_repair.py` before trusting the support number. "
          "Refresh with `python tools/mesh_index.py <dir>`.", "",
          "| file | tris | watertight | height | footprint (x × y) | needs support | look |",
          "|---|---:|:---:|---:|---:|---:|---|", *rows, ""]
    (d / "index.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
    print("wrote", d / "index.md", f"({len(rows)} meshes)")

if __name__ == "__main__":
    main()
