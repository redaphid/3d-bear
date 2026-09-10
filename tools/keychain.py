#!/usr/bin/env python
"""Stage 5 — keychain: scale a validated bear STL and fuse a hanging loop onto the top of its head.

    python tools/keychain.py print-ready/bear-r4b-grizzly-roar-arms-up-on-rock-160mm.stl \
        --out print-ready/keychain-bear-r4b-32mm.stl --scale 0.2 [--hole 4.5] [--tube 2.2] [--plane front|side] [--views]

- The input must already be a validated solid (the Stage-3 output). The base stays closed: at
  keychain scale the piece prints solid, there is no pole or light.
- The head top is found as the highest point of the mesh inside the central column (|x| < 18 % of
  the width around the bear's centre), which ignores raised paws.
- The ring is a torus (hole diameter --hole, tube diameter --tube, in printed mm) whose plane is
  vertical: --plane front puts the hole facing the viewer (a pendant bail, chain runs front-to-back),
  --plane side puts the hole facing sideways (chain runs left-right). It sinks --sink mm into the
  head so the union is one body, then the result is validated with manifold3d.
"""
from __future__ import annotations

import argparse
import sys
import time

import numpy as np
import trimesh


def log(msg: str) -> None:
    print(f"  {msg}")


def validate(m: trimesh.Trimesh, label: str) -> None:
    from manifold3d import Manifold, Mesh as MMesh
    ok = Manifold(MMesh(vert_properties=m.vertices.astype(np.float32), tri_verts=m.faces.astype(np.uint32))).status().name
    log(f"{label:10s} watertight {m.is_watertight}  winding {m.is_winding_consistent}  euler {m.euler_number}  manifold3d {ok}  bodies {m.body_count}")
    if not (m.is_watertight and m.is_winding_consistent and ok == "NoError"):
        raise SystemExit(f"{label}: not a valid solid")


def _boolean(a: trimesh.Trimesh, b: trimesh.Trimesh, op: str) -> trimesh.Trimesh:
    from manifold3d import Manifold, Mesh as MMesh
    ma = Manifold(MMesh(vert_properties=a.vertices.astype(np.float32), tri_verts=a.faces.astype(np.uint32)))
    mb = Manifold(MMesh(vert_properties=b.vertices.astype(np.float32), tri_verts=b.faces.astype(np.uint32)))
    r = ((ma + mb) if op == "union" else (ma - mb)).to_mesh()
    m = trimesh.Trimesh(np.asarray(r.vert_properties)[:, :3], np.asarray(r.tri_verts), process=False)
    m.merge_vertices()
    parts = m.split(only_watertight=False)
    if len(parts) > 1:
        parts = sorted(parts, key=lambda p: p.volume, reverse=True)
        log(f"{op} produced {len(parts)} bodies; kept the largest ({parts[0].volume:.0f} mm^3)")
        m = parts[0]
    m.fix_normals()
    return m


def union(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    return _boolean(a, b, "union")


def difference(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    return _boolean(a, b, "difference")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=float, default=0.2, help="scale factor from the input (0.2 = 20 percent)")
    ap.add_argument("--hole", type=float, default=4.5, help="hole diameter of the loop, mm printed")
    ap.add_argument("--tube", type=float, default=2.2, help="tube (wire) diameter of the loop, mm printed")
    ap.add_argument("--sink", type=float, default=1.2, help="how far the loop sinks into the head, mm")
    ap.add_argument("--plane", choices=["front", "side"], default="front")
    ap.add_argument("--style", choices=["torus", "bail"], default="torus",
                    help="torus = a ring (min section is 2 tube circles); bail = a slab with a drilled hole (min section is 2 x thickness x web)")
    ap.add_argument("--thickness", type=float, default=4.0, help="bail only: slab thickness along the hole axis, mm")
    ap.add_argument("--web", type=float, default=3.0, help="bail only: material either side of the hole, mm")
    ap.add_argument("--column", type=float, default=0.18, help="half-width of the central column as a fraction of the model width")
    ap.add_argument("--views", action="store_true")
    a = ap.parse_args()

    t0 = time.time()
    m = trimesh.load(a.stl, force="mesh")
    log(f"input      {len(m.faces):,} faces  extents {np.round(m.extents, 1)} mm")
    validate(m, "input")

    m.apply_scale(a.scale)
    lo = m.bounds[0]; m.apply_translation(-lo)          # plate at z = 0
    ext = m.extents
    log(f"scaled     x{a.scale:g} -> {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} mm")

    # head top: highest vertex in the central column
    cx = m.bounds[0][0] + ext[0] / 2
    col = np.abs(m.vertices[:, 0] - cx) < a.column * ext[0]
    v = m.vertices[col]
    top = v[np.argmax(v[:, 2])]
    # centre the ring over the head in y as well: take the mean y of the top 1 mm of the column
    cap = v[v[:, 2] > top[2] - 1.0]
    cy = float(cap[:, 1].mean())
    log(f"head top   z {top[2]:.1f} mm at x {cx:.1f}, y {cy:.1f}  (column |x| < {a.column * ext[0]:.1f} mm; model top {ext[2]:.1f} mm)")

    axis = [0, 1, 0] if a.plane == "front" else [1, 0, 0]
    # rotation that takes the canonical +z axis of a cylinder onto the hole axis
    to_axis = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]) if a.plane == "front" \
        else trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0])

    if a.style == "torus":
        major = (a.hole + a.tube) / 2      # centre-line radius
        minor = a.tube / 2
        ring = trimesh.creation.torus(major_radius=major, minor_radius=minor, major_sections=64, minor_sections=24)
        ring.apply_transform(to_axis)
        zc = top[2] - a.sink + major + minor                                   # bottom of tube sinks into the head
        ring.apply_translation([cx, cy, zc])
        log(f"loop       torus: hole {a.hole:g} mm, tube {a.tube:g} mm, outer {2 * (major + minor):.1f} mm, "
            f"plane {a.plane}, top z {zc + major + minor:.1f}; min section 2 x pi r^2 = {2 * np.pi * minor**2:.1f} mm^2")
    else:
        # A solid bail: a rounded-top slab standing on the head with a hole drilled through it.
        # The material either side of the hole is a rectangle, so its area is set by
        # thickness x web rather than by a tube's circle — that is the whole point.
        hole_r = a.hole / 2
        r_out = hole_r + a.web
        t = a.thickness
        zc = top[2] + hole_r + 0.5                                             # keep the hole clear of the skull
        z_bottom = top[2] - a.sink
        disc = trimesh.creation.cylinder(radius=r_out, height=t, sections=64)
        disc.apply_transform(to_axis); disc.apply_translation([cx, cy, zc])
        neck_h = zc - z_bottom
        size = [2 * r_out, t, neck_h] if a.plane == "front" else [t, 2 * r_out, neck_h]
        neck = trimesh.creation.box(extents=size)
        neck.apply_translation([cx, cy, z_bottom + neck_h / 2])
        bail = union(disc, neck)
        hole = trimesh.creation.cylinder(radius=hole_r, height=t * 4, sections=64)
        hole.apply_transform(to_axis); hole.apply_translation([cx, cy, zc])
        bail = difference(bail, hole)
        ring = bail
        log(f"loop       bail: hole {a.hole:g} mm, thickness {t:g} mm, web {a.web:g} mm, outer {2 * r_out:.1f} mm, "
            f"plane {a.plane}, top z {zc + r_out:.1f}; min section 2 x t x web = {2 * t * a.web:.1f} mm^2")

    out = union(m, ring)
    validate(out, "union")
    out.export(a.out)
    ext2 = out.extents
    log(f"wrote {a.out}  {len(out.faces):,} faces  {ext2[0]:.1f} x {ext2[1]:.1f} x {ext2[2]:.1f} mm  ({time.time() - t0:.1f} s)")

    if a.views:
        import subprocess
        png = a.out.rsplit(".", 1)[0] + "_views.png"
        subprocess.run([sys.executable, "tools/mesh_views.py", a.out, "--out", png, "--height", f"{ext2[2]:.2f}"], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
