#!/usr/bin/env python3
"""
check_mesh.py — is this thing printable?

Point it at whatever came out of ComfyUI. It answers the four questions that
decide whether the next three hours of printer time are worth spending:

    is it solid, how big is it, how much of it hangs over nothing,
    and where.

    python check_mesh.py bear.glb
    python check_mesh.py bear.stl --height 160 --export bear_scaled.stl

The overhang census is the useful part. Slicers will happily generate
supports for a surface that shouldn't exist, and on a piece meant to glow
every support scar is a dead patch. Better to know the number before you
find out in the dark.

    pip install trimesh manifold3d numpy
"""

import argparse
import sys

import numpy as np
import trimesh

LIMIT_DEG = 45.0  # steeper than this carries itself; shallower needs help


def load(path):
    """Accept anything trimesh reads; flatten scenes down to one mesh."""
    loaded = trimesh.load(path, force="mesh")
    if isinstance(loaded, trimesh.Scene):
        loaded = trimesh.util.concatenate(loaded.dump())
    if not isinstance(loaded, trimesh.Trimesh) or loaded.is_empty:
        raise SystemExit(f"nothing mesh-shaped in {path}")
    return loaded


def overhang_census(mesh, limit_deg=LIMIT_DEG, plate_tol=1e-3):
    """
    Area-weighted survey of downward-facing surface.

    Angles are from horizontal: 90 is a wall and prints perfectly, 0 is a
    ceiling and prints as spaghetti. The build plate is not an overhang, so
    faces resting on the lowest z are excused.
    """
    normals, areas = mesh.face_normals, mesh.area_faces
    tri_z = mesh.vertices[mesh.faces][:, :, 2]
    on_plate = np.all(tri_z <= mesh.bounds[0][2] + plate_tol, axis=1)

    downward = (normals[:, 2] < 0) & ~on_plate
    angles = np.degrees(np.arccos(np.clip(-normals[:, 2], 0.0, 1.0)))
    bad = downward & (angles < limit_deg)

    total = float(areas.sum())
    return {
        "worst": float(angles[downward].min()) if downward.any() else 90.0,
        "area": float(areas[bad].sum()),
        "pct": 100.0 * float(areas[bad].sum()) / total if total else 0.0,
        "mask": bad,
        "angles": angles,
    }


def where_is_it(mesh, census, bands=6):
    """Overhang broken out by height, so you know whether it's the jaw."""
    bad, areas = census["mask"], mesh.area_faces
    if not bad.any():
        return []
    lo, hi = mesh.bounds[0][2], mesh.bounds[1][2]
    edges = np.linspace(lo, hi, bands + 1)
    centers = mesh.triangles_center[bad]
    out = []
    for i in range(bands):
        sel = (centers[:, 2] >= edges[i]) & (centers[:, 2] < edges[i + 1] + 1e-9)
        if sel.any():
            out.append((edges[i], edges[i + 1], float(areas[bad][sel].sum()),
                        float(census["angles"][bad][sel].min())))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("--height", type=float,
                    help="uniformly scale to this height in mm and re-measure")
    ap.add_argument("--export", help="write the (possibly scaled) mesh here")
    ap.add_argument("--limit", type=float, default=LIMIT_DEG,
                    help=f"overhang threshold in degrees (default {LIMIT_DEG})")
    args = ap.parse_args()

    mesh = load(args.path)
    mesh.merge_vertices()

    if args.height:
        mesh.apply_scale(args.height / mesh.extents[2])
    mesh.apply_translation([0.0, 0.0, -mesh.bounds[0][2]])

    lo, hi = mesh.bounds
    census = overhang_census(mesh, args.limit)

    print(f"\n{args.path}")
    print(f"  triangles      {len(mesh.faces):,}")
    print(f"  watertight     {mesh.is_watertight}"
          f"{'' if mesh.is_watertight else '   <-- repair before slicing'}")
    print(f"  winding ok     {mesh.is_winding_consistent}")
    print(f"  footprint      {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} mm")
    print(f"  height         {hi[2]-lo[2]:.1f} mm")
    if mesh.is_watertight:
        print(f"  solid volume   {mesh.volume/1000.0:.1f} cm^3")
    print(f"  worst overhang {census['worst']:.1f} deg from horizontal")
    print(f"  needs support  {census['pct']:.2f}% of surface "
          f"({census['area']:.1f} mm^2)")

    bands = where_is_it(mesh, census)
    if bands:
        print("\n  where:")
        for z0, z1, area, worst in bands:
            print(f"    z {z0:6.1f}-{z1:6.1f} mm   {area:7.1f} mm^2   "
                  f"worst {worst:4.1f} deg")

    if len(mesh.faces) > 50_000:
        print("\n  note: dense for a print. decimating hard is free speed,"
              "\n        and flat facets read better under UV than smooth ones.")

    print()
    if args.export:
        mesh.export(args.export)
        print(f"wrote {args.export}\n")

    # non-zero exit if a slicer would fight you, so this can gate a script
    return 0 if (mesh.is_watertight and census["pct"] < 5.0) else 1


if __name__ == "__main__":
    sys.exit(main())
