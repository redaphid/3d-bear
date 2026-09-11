#!/usr/bin/env python
"""Stage 5 — keychain: scale a validated bear STL and give it something to hang from.

    python tools/keychain.py print-ready/bear-r4b-grizzly-roar-arms-up-on-rock-160mm.stl \
        --out print-ready/keychain-bear-r4b-32mm.stl --scale 0.2 [--hole 4.5] [--tube 2.2] [--plane front|side] [--views]

- The input must already be a validated solid (the Stage-3 output). The base stays closed: at
  keychain scale the piece prints solid, there is no pole or light.
- The head top is found as the highest point of the mesh inside the central column (|x| < 18 % of
  the width around the bear's centre), which ignores raised paws.
- --style hole (recommended for a thin stretch cord) bores a --hole mm tunnel straight through the
  figure at --hole-z of its height. No added geometry, and the load is carried by the whole
  section there (about 55 mm^2) instead of by a thin loop (14 mm^2 for a 3 mm ring).
- --nfc recesses an NTAG215 sticker pocket (10.5 x 0.8 mm, spec from D:/Projects/nfc-bead) into the underside
  of the plinth after adding a --riser (1.5 mm) so the floor over the chip stays thick; the pocket centre is
  the point of the base outline with the most clearance and it must pass the recipe's 16-point perimeter check.
- --style bail makes a slab with a drilled hole; --style torus makes a ring. For a ring the
  weak point is its own widest line, two bare tube circles, and sinking it deeper does NOT help.
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
    # manifold3d output is already consistently oriented, including cavity skins (an embedded NFC
    # pocket is one). Keep every body except zero-volume debris; never per-body fix normals — that
    # would flip a cavity into a second solid.
    parts = m.split(only_watertight=False)
    if len(parts) > 1:
        keep = [p for p in parts if abs(p.volume) >= 0.5]
        if len(keep) < len(parts):
            log(f"{op}: dropped {len(parts) - len(keep)} debris bodies under 0.5 mm^3")
        m = trimesh.util.concatenate(keep) if len(keep) > 1 else keep[0]
    if m.volume < 0:
        m.invert()
    return m


def union(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    return _boolean(a, b, "union")


def difference(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    return _boolean(a, b, "difference")


def nfc_pocket(out, a):
    """Riser under the base outline, then a sticker pocket recessed into its underside."""
    from shapely.geometry import Polygon, Point
    lo = out.bounds[0]
    sec = out.section(plane_origin=[0, 0, lo[2] + 0.1], plane_normal=[0, 0, 1])
    polys = sorted([Polygon(l[:, :2]) for l in sec.discrete if len(l) > 3], key=lambda q: q.area, reverse=True)
    base = polys[0].buffer(0)
    # best centre = the point of the outline with the largest clearance (a 0.25 mm grid search)
    b = base.bounds; best = None
    for x in np.arange(b[0], b[2], 0.25):
        for y in np.arange(b[1], b[3], 0.25):
            pt = Point(x, y)
            if base.contains(pt):
                d = base.exterior.distance(pt)
                if best is None or d > best[0]:
                    best = (d, x, y)
    clear, cx, cy = best
    r = a.nfc_diameter / 2
    wall = clear - r
    if wall < 1.0:
        raise SystemExit(f"NFC pocket does not fit: {a.nfc_diameter:g} mm pocket leaves {wall:.2f} mm of wall (need >= 1.0); shrink --nfc-diameter or enlarge the plinth")
    # 16-point perimeter check, as the bead recipe does
    misses = [k for k in range(16) if not base.contains(Point(cx + r * np.cos(k * np.pi / 8), cy + r * np.sin(k * np.pi / 8)))]
    if misses:
        raise SystemExit(f"NFC perimeter check failed at points {misses}")
    # inset the outline 0.1 mm so the riser's side wall is never coincident with the bear's (coincident
    # walls leave sliver triangles that manifold3d tolerates but slicers and trimesh flag)
    riser = trimesh.creation.extrude_polygon(base.buffer(-0.1), a.riser + 0.3)   # +0.3 overlaps into the bear
    riser.apply_translation([0, 0, lo[2] - a.riser])
    out = union(out, riser)
    plate_z = lo[2] - a.riser                                   # the new bottom of the plinth
    if a.nfc_mode == "embed":
        # a sealed cavity: floor of --nfc-floor above the plate, --nfc-depth tall, plinth above it
        pocket = trimesh.creation.cylinder(radius=r, height=a.nfc_depth, sections=96)
        pocket.apply_translation([cx, cy, plate_z + a.nfc_floor + a.nfc_depth / 2])
        top = a.nfc_floor + a.nfc_depth
        ceiling = (a.riser + 1.8) - top                             # ~1.8 mm is the plinth at 20 %
        if ceiling < 0.8:
            raise SystemExit(f"only {ceiling:.1f} mm of plinth above the pocket; raise --riser")
        pause = f"PAUSE the print at {top:.1f} mm (after layer {round(top / 0.2)} at 0.2 mm layers), drop the sticker in face-down, resume; the next layer bridges over it"
    else:
        pocket = trimesh.creation.cylinder(radius=r, height=a.nfc_depth + 2.0, sections=96)
        pocket.apply_translation([cx, cy, plate_z + a.nfc_depth - (a.nfc_depth + 2.0) / 2])
        ceiling = (a.riser + 1.8) - a.nfc_depth
        pause = "open recess in the underside; glue the sticker in"
    out = difference(out, pocket)
    out.apply_translation([0, 0, -out.bounds[0][2]])
    log(f"nfc pocket {a.nfc_mode}: {a.nfc_diameter:g} x {a.nfc_depth:g} mm at ({cx:.1f}, {cy:.1f}), wall {wall:.1f} mm all round (16/16 perimeter points inside); "
        f"riser {a.riser:g} mm under a {base.area:.0f} mm^2 plinth -> plate {a.riser + 1.8:.1f} mm thick, "
        f"{a.nfc_floor if a.nfc_mode == 'embed' else 0:.1f} mm floor, {ceiling:.1f} mm over the chip. {pause}")
    validate(out, "nfc")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=float, default=0.2, help="scale factor from the input (0.2 = 20 percent)")
    ap.add_argument("--hole", type=float, default=4.5, help="hole diameter of the loop, mm printed")
    ap.add_argument("--tube", type=float, default=2.2, help="tube (wire) diameter of the loop, mm printed")
    ap.add_argument("--sink", type=float, default=1.2, help="how far the loop sinks into the head, mm")
    ap.add_argument("--plane", choices=["front", "side"], default="front")
    ap.add_argument("--style", choices=["torus", "bail", "hole"], default="torus",
                    help="torus = a ring; bail = a slab with a drilled hole; hole = bore straight through the head, no added geometry")
    ap.add_argument("--thickness", type=float, default=4.0, help="bail only: slab thickness along the hole axis, mm")
    ap.add_argument("--web", type=float, default=3.0, help="bail only: material either side of the hole, mm")
    ap.add_argument("--hole-z", type=float, default=0.90, help="hole style only: height of the bore as a fraction of the model height")
    ap.add_argument("--through", choices=["head", "all"], default="head",
                    help="hole style only: head = bore only the central island and stop inside the gaps to the arms; all = full width")
    ap.add_argument("--column", type=float, default=0.18, help="half-width of the central column as a fraction of the model width")
    ap.add_argument("--nfc", action="store_true", help="recess an NFC sticker pocket into the underside of the plinth (NTAG215 spec from D:/Projects/nfc-bead)")
    ap.add_argument("--nfc-mode", choices=["embed", "open"], default="embed",
                    help="embed = sealed cavity inside the plinth: pause the print at the reported height, drop the sticker in, resume (default); open = recess in the underside, sticker glued in")
    ap.add_argument("--nfc-diameter", type=float, default=11.0, help="pocket diameter, mm (10 mm sticker; 11.0 so it drops in by hand mid-print, holes print ~0.3 mm small)")
    ap.add_argument("--nfc-depth", type=float, default=1.0, help="pocket depth, mm (sticker is ~0.4; the rest is air so the bridge over it lands clean)")
    ap.add_argument("--nfc-floor", type=float, default=1.2, help="embed only: solid floor under the pocket, mm (6 layers at 0.2)")
    ap.add_argument("--riser", type=float, default=2.0, help="extra plinth thickness added under the base, mm (the plinth alone is ~1.8 mm at 20 %%)")
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

    if a.style == "hole":
        # No added hardware: bore a cord hole straight through the head. Strongest option by far,
        # because the load is carried by the whole skull section rather than by a thin added loop.
        z_drill = m.bounds[0][2] + a.hole_z * ext[2]
        # Find the head as its own island in the slice at that height (the raised arms are separate
        # islands either side of it), bore through the head only, and stop the bore inside the gaps
        # between head and arms so the cord exits there instead of piercing the arms.
        def islands(mesh):
            s = mesh.section(plane_origin=[0, 0, z_drill], plane_normal=[0, 0, 1])
            p2, T = s.to_2D()
            out = []
            for poly in p2.polygons_full:
                pts = trimesh.transform_points(np.c_[np.array(poly.exterior.coords), np.zeros(len(poly.exterior.coords))], T)
                out.append(dict(cx=pts[:, 0].mean(), cy=pts[:, 1].mean(), x0=pts[:, 0].min(), x1=pts[:, 0].max(),
                                y0=pts[:, 1].min(), y1=pts[:, 1].max(), area=abs(poly.area)))
            return out
        isl = islands(m)
        head = min(isl, key=lambda i: abs(i["cx"] - cx))
        others = [i for i in isl if i is not head]
        if a.plane == "side":
            lo, hi = head["x0"], head["x1"]
            gap = min([head["x0"] - i["x1"] for i in others if i["x1"] <= head["x0"]] +
                      [i["x0"] - head["x1"] for i in others if i["x0"] >= head["x1"]] + [99.0])
        else:
            lo, hi = head["y0"], head["y1"]
            gap = min([head["y0"] - i["y1"] for i in others if i["y1"] <= head["y0"]] +
                      [i["y0"] - head["y1"] for i in others if i["y0"] >= head["y1"]] + [99.0])
        margin = min(1.5, 0.6 * gap) if a.through == "head" else float(np.abs(ext).max())
        length = (hi - lo) + 2 * margin
        bore = trimesh.creation.cylinder(radius=a.hole / 2, height=length, sections=64)
        bore.apply_transform(to_axis)
        bore.apply_translation([head["cx"], head["cy"], z_drill])
        out = difference(m, bore)
        validate(out, "bored")
        rem = min((i["area"] for i in islands(out) if abs(i["cx"] - cx) < 3.0), default=float("nan"))
        log(f"cord hole  {a.hole:g} mm through the {a.through} at z {z_drill:.1f} mm ({a.hole_z:.0%}), axis {a.plane}; "
            f"head island {hi - lo:.1f} mm wide, {head['area']:.0f} mm^2, gap to arms {gap:.1f} mm; "
            f"bore {length:.1f} mm long; skull section left around the bore {rem:.1f} mm^2")
        if a.nfc:
            out = nfc_pocket(out, a)
        out.export(a.out)
        e = out.extents
        log(f"wrote {a.out}  {len(out.faces):,} faces  {e[0]:.1f} x {e[1]:.1f} x {e[2]:.1f} mm  ({time.time() - t0:.1f} s)")
        if a.views:
            import subprocess
            png = a.out.rsplit(".", 1)[0] + "_views.png"
            subprocess.run([sys.executable, "tools/mesh_views.py", a.out, "--out", png, "--height", f"{e[2]:.2f}"], check=False)
        return 0

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
    if a.nfc:
        out = nfc_pocket(out, a)
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
