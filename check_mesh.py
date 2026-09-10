#!/usr/bin/env python3
"""
check_mesh.py — is this thing printable?

Point it at whatever came out of ComfyUI. It answers the four questions that
decide whether the next three hours of printer time are worth spending:

    is it solid, how big is it, how much of it hangs over nothing,
    and where.

    python check_mesh.py bear.glb
    python check_mesh.py bear.stl --height 160 --export bear_scaled.stl
    python check_mesh.py bear.glb --up y          # force the up axis

The overhang census is the useful part. Slicers will happily generate
supports for a surface that shouldn't exist, and on a piece meant to glow
every support scar is a dead patch. Better to know the number before you
find out in the dark.

Up axis: glTF/GLB is Y-up by spec; STL, slicers and this script are Z-up.
Measure a Y-up mesh as if it were Z-up and the bear is lying on its back —
the footprint, the height and every overhang number after that are fiction.
`--up auto` (default) rotates .glb/.gltf onto their feet before measuring;
`--export` writes the mesh as measured (Z-up, scaled, on the plate).

    pip install trimesh manifold3d numpy
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import trimesh

LIMIT_DEG = 45.0  # steeper than this carries itself; shallower needs help
UP_CHOICES = ("y", "z", "auto")
Y_UP_SUFFIXES = {".glb", ".gltf"}


def load(path):
    """Accept anything trimesh reads; flatten scenes down to one mesh."""
    loaded = trimesh.load(path, force="mesh")
    if isinstance(loaded, trimesh.Scene):
        loaded = trimesh.util.concatenate(loaded.dump())
    if not isinstance(loaded, trimesh.Trimesh) or loaded.is_empty:
        raise SystemExit(f"nothing mesh-shaped in {path}")
    return loaded


def guess_up(path, up="auto"):
    """glTF is Y-up by spec; everything a slicer reads is Z-up."""
    if up == "auto":
        return "y" if Path(path).suffix.lower() in Y_UP_SUFFIXES else "z"
    return up


def orient_z_up(mesh, up="z"):
    """
    Stand a Y-up mesh on its feet: +Y -> +Z, +Z -> -Y.

    glTF's "forward" is +Z, so after the rotation the model faces -Y, which
    is what Blender and the slicers call the front. Z-up input is untouched.
    """
    if up == "y":
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    return mesh


def prepare(mesh, up="z", height=None):
    """Merge, orient, scale, and set on the plate: the state every measurement assumes."""
    mesh.merge_vertices()
    orient_z_up(mesh, up)
    if height:
        mesh.apply_scale(height / mesh.extents[2])
    mesh.apply_translation([0.0, 0.0, -mesh.bounds[0][2]])
    return mesh


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


def measure(mesh, limit_deg=LIMIT_DEG):
    """Everything the report prints, as a dict, so other tools can reuse it."""
    lo, hi = mesh.bounds
    census = overhang_census(mesh, limit_deg)
    bands = where_is_it(mesh, census)
    return {
        "faces": len(mesh.faces),
        "watertight": bool(mesh.is_watertight),
        "winding_ok": bool(mesh.is_winding_consistent),
        "footprint": (float(hi[0] - lo[0]), float(hi[1] - lo[1])),
        "height": float(hi[2] - lo[2]),
        "volume_cm3": float(mesh.volume / 1000.0) if mesh.is_watertight else None,
        "worst_deg": census["worst"],
        "unsupported_pct": census["pct"],
        "unsupported_area": census["area"],
        "bands": bands,                                    # (z0, z1, area, worst)
        "worst_band": max(bands, key=lambda b: b[2]) if bands else None,
    }


def print_report(path, info, up=None):
    print(f"\n{path}")
    if up:
        print(f"  up axis        {up}{'  (rotated to z-up)' if up == 'y' else ''}")
    print(f"  triangles      {info['faces']:,}")
    print(f"  watertight     {info['watertight']}"
          f"{'' if info['watertight'] else '   <-- repair before slicing'}")
    print(f"  winding ok     {info['winding_ok']}")
    print(f"  footprint      {info['footprint'][0]:.1f} x {info['footprint'][1]:.1f} mm")
    print(f"  height         {info['height']:.1f} mm")
    if info["volume_cm3"] is not None:
        print(f"  solid volume   {info['volume_cm3']:.1f} cm^3")
    print(f"  worst overhang {info['worst_deg']:.1f} deg from horizontal")
    print(f"  needs support  {info['unsupported_pct']:.2f}% of surface "
          f"({info['unsupported_area']:.1f} mm^2)")

    if info["bands"]:
        print("\n  where:")
        for z0, z1, area, worst in info["bands"]:
            print(f"    z {z0:6.1f}-{z1:6.1f} mm   {area:7.1f} mm^2   "
                  f"worst {worst:4.1f} deg")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--height", type=float,
                    help="uniformly scale to this height in mm and re-measure")
    ap.add_argument("--export", help="write the (oriented, possibly scaled) mesh here")
    ap.add_argument("--limit", type=float, default=LIMIT_DEG,
                    help=f"overhang threshold in degrees (default {LIMIT_DEG})")
    ap.add_argument("--up", choices=UP_CHOICES, default="auto",
                    help="which axis is up in the file; auto = y for .glb/.gltf, "
                         "z for everything else")
    args = ap.parse_args()

    up = guess_up(args.path, args.up)
    mesh = prepare(load(args.path), up, args.height)
    info = measure(mesh, args.limit)
    print_report(args.path, info, up)

    if info["faces"] > 50_000:
        print("\n  note: dense for a print. decimating hard is free speed,"
              "\n        and flat facets read better under UV than smooth ones.")

    print()
    if args.export:
        mesh.export(args.export)
        print(f"wrote {args.export}\n")

    # non-zero exit if a slicer would fight you, so this can gate a script
    return 0 if (info["watertight"] and info["unsupported_pct"] < 5.0) else 1


if __name__ == "__main__":
    sys.exit(main())
