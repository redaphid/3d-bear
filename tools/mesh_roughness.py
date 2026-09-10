#!/usr/bin/env python3
"""
mesh_roughness.py — how much surface detail does a mesh actually carry?

    python tools/mesh_roughness.py a.glb b.glb --height 160

Every mesh is scaled to the same printed height first, so the numbers compare
across generators. The dihedral angle between neighbouring faces is the
measure: a smooth blob has a mean of a degree or two and a thin p99 tail; carved
fur, folds and claws push the tail out. Face count and surface area come along
because a mesh with more faces at the same area has room to carry more of that
detail (and because a generator that hallucinates internal shells shows up as
area that is not on the outside).

Reported per mesh: faces, area (mm²), dihedral mean / p90 / p99 (degrees).
"""

import argparse
import sys

import numpy as np
import trimesh


def load(path):
    m = trimesh.load(path, force="mesh", process=False)
    if isinstance(m, trimesh.Scene):
        m = trimesh.util.concatenate([g for g in m.geometry.values()])
    return m


def measure(path, height):
    m = load(path)
    m.merge_vertices()
    if height:
        ext = m.bounds[1] - m.bounds[0]
        m.apply_scale(height / ext.max())
    ang = np.degrees(m.face_adjacency_angles)
    return {
        "path": path,
        "faces": len(m.faces),
        "area_mm2": float(m.area),
        "mean": float(ang.mean()),
        "p90": float(np.percentile(ang, 90)),
        "p99": float(np.percentile(ang, 99)),
        "watertight": bool(m.is_watertight),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("meshes", nargs="+")
    ap.add_argument("--height", type=float, default=160.0, help="scale the longest extent to this many mm (0 = leave)")
    a = ap.parse_args()
    print(f"{'mesh':48} {'faces':>9} {'area mm2':>10} {'mean':>6} {'p90':>6} {'p99':>6}  wt")
    for p in a.meshes:
        r = measure(p, a.height)
        name = r["path"] if len(r["path"]) <= 48 else "..." + r["path"][-45:]
        print(f"{name:48} {r['faces']:>9,} {r['area_mm2']:>10,.0f} {r['mean']:>6.2f} {r['p90']:>6.2f} {r['p99']:>6.2f}  {'y' if r['watertight'] else 'n'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
