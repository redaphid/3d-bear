#!/usr/bin/env python
"""Stage 4 prep — hollow a validated bear into a shell of uniform wall for a light inside.

    python tools/hollow.py print-ready/bear-r4b-TRELLIS-grizzly-roar-on-rock-160mm.stl \
        --out print-ready/totem-bear-r4b-TRELLIS-160mm-hollow-2mm.stl --wall 2.0 [--pitch 0.4] [--height 160] [--views]

Why a modelled shell rather than slicer settings: a uniform wall lets the UV light inside reach the
phosphor evenly, the slicer prints proper skins on both surfaces, and thin features (ears, claws)
stay solid automatically because the erosion never reaches them.

How: voxelise the solid at --pitch, take the Euclidean distance from the outside, keep only the
voxels within --wall of the surface, re-extract the surface (two nested skins), then cut the bottom
--wall mm off so the cavity opens through the plinth for the pole and the light. The input is
scaled to --height + --wall first so the finished piece is exactly --height tall. Validated with
manifold3d like every Stage-3 output. Also reports the material volume as a filament estimate.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage
from skimage import measure

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import mesh_repair as mr  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--wall", type=float, default=2.0, help="wall thickness, mm printed")
    ap.add_argument("--pitch", type=float, default=0.4, help="voxel pitch, mm")
    ap.add_argument("--height", type=float, default=None, help="printed height, mm (default: keep the input height)")
    ap.add_argument("--faces", type=int, default=80000, help="face budget after hollowing (two skins)")
    ap.add_argument("--density", type=float, default=1.24, help="g/cm^3 for the filament estimate")
    ap.add_argument("--views", action="store_true")
    a = ap.parse_args()
    t0 = time.time()

    m = trimesh.load(a.stl, force="mesh")
    v = mr.validate(m)
    mr.log("input", f"{len(m.faces):,} faces  {mr.validation_line(v)}")
    if not mr.is_solid(v):
        raise SystemExit("input must be a validated solid (run mesh_repair.py first)")
    height = a.height or float(m.extents[2])
    m = mr.scale_and_place(m, height + a.wall)          # bottom --wall mm is cut away at the end
    solid_volume = m.volume

    # ---- voxelise, distance from outside, keep the skin ---------------------------------------
    t = time.time()
    vg = m.voxelized(a.pitch).fill()
    S = np.pad(vg.matrix.astype(bool), 2)
    origin = vg.translation - 2 * a.pitch
    dist = ndimage.distance_transform_edt(S) * a.pitch
    inner = dist > a.wall
    # keep only the main cavity: isolated pockets inside thick regions would become extra closed
    # skins that the decimator later drops or breaks on. They are filled back in as solid.
    lab, n_cav = ndimage.label(inner)
    if n_cav > 1:
        sizes = ndimage.sum(inner, lab, range(1, n_cav + 1))
        inner = lab == (int(np.argmax(sizes)) + 1)
    shell = S & ~inner
    mr.log("hollow", f"grid {S.shape}, {S.sum():,} solid voxels -> {shell.sum():,} shell voxels at wall {a.wall:g} mm "
                     f"({shell.sum() / S.sum():.0%} of the material); {n_cav} cavity pocket(s), kept the largest  ({time.time() - t:.1f} s)")

    t = time.time()
    field = ndimage.gaussian_filter(shell.astype(np.float32), 0.6)
    verts, faces, _, _ = measure.marching_cubes(field, level=0.5)
    sh = trimesh.Trimesh(verts[:, [0, 1, 2]] * a.pitch + origin, faces, process=True)
    sh.update_faces(sh.nondegenerate_faces()); sh.update_faces(sh.unique_faces())
    parts = sorted(sh.split(only_watertight=False), key=lambda p: len(p.faces), reverse=True)
    if len(parts) > 2:
        debris = ", ".join(f"{len(p.faces):,}" for p in parts[2:])
        mr.log("extract", f"{len(parts)} skins; keeping the outer and inner ({len(parts[0].faces):,} / {len(parts[1].faces):,} faces), dropping debris of {debris} faces")
        sh = trimesh.util.concatenate(parts[:2])
    # Marching cubes orients both skins from material toward air: outer faces out, inner faces
    # into the cavity. That is the correct hollow-solid orientation; do NOT run a per-body
    # winding fix here (it would flip the cavity into a second solid). Just check the sign.
    if sh.volume < 0:
        sh.invert()
    expect = shell.sum() * a.pitch ** 3
    mr.log("extract", f"marching cubes: {len(sh.faces):,} faces, {sh.body_count} skins, volume {sh.volume / 1000:.0f} cm^3 "
                      f"(voxel estimate {expect / 1000:.0f})  ({time.time() - t:.1f} s)")

    # Decimate each skin on its own with a quadric collapse (the outer keeps most of the budget;
    # nobody sees the inside). A global simplify with a tolerance near the wall thickness pushes
    # the skins through each other, so that is avoided entirely.
    t = time.time()
    skins = sorted(sh.split(only_watertight=False), key=lambda p: len(p.faces), reverse=True)
    budget = [int(a.faces * 0.65), int(a.faces * 0.35)]
    out_skins = []
    for skin, target in zip(skins, budget):
        inverted = skin.volume < 0             # the cavity skin faces inward; decimate it as a normal solid
        if inverted:
            skin = skin.copy(); skin.invert()
        d = mr.decimate(skin, target)          # quadric first, manifold3d simplify if that breaks the skin
        if not d.is_watertight or len(d.faces) < target // 4:
            raise SystemExit(f"skin decimation broke a skin ({len(skin.faces):,} -> {len(d.faces):,} faces)")
        if d.volume < 0:
            d.invert()
        if inverted:
            d.invert()                         # back to facing the cavity
        out_skins.append(d)
    sh = trimesh.util.concatenate(out_skins)
    mr.log("decimate", f"skins {len(skins[0].faces):,}/{len(skins[1].faces):,} -> {len(out_skins[0].faces):,}/{len(out_skins[1].faces):,} faces, "
                       f"volume {sh.volume / 1000:.0f} cm^3  ({time.time() - t:.1f} s)")

    # ---- open the base: cut the bottom --wall mm so the cavity is reachable --------------------
    # Direct manifold3d subtraction: trimesh's boolean wrapper re-orients the inner skin into a
    # second solid, which is exactly what must not happen to a cavity.
    lo, hi = sh.bounds
    box = trimesh.creation.box(extents=[hi[0] - lo[0] + 20, hi[1] - lo[1] + 20, a.wall + 10])
    box.apply_translation([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2] + a.wall - (a.wall + 10) / 2])
    cut = mr.from_manifold(mr.to_manifold(sh) - mr.to_manifold(box), process=False)
    cut.apply_translation([0, 0, -cut.bounds[0][2]])
    cut.merge_vertices()
    sh = cut
    mr.log("open base", f"removed bottom {a.wall:g} mm (manifold3d); {sh.body_count} body, volume {sh.volume / 1000:.0f} cm^3; {mr.describe_openings(sh)}")
    v = mr.validate(sh)
    mr.log("validate", mr.validation_line(v))
    if not mr.is_solid(v):
        raise SystemExit("shell is not a valid solid after the base cut")

    e = sh.extents
    grams = sh.volume / 1000.0 * a.density
    mr.log("material", f"shell {sh.volume / 1000:.0f} cm^3 vs solid {solid_volume / 1000:.0f} cm^3 -> about {grams:.0f} g of filament at {a.density:g} g/cm^3")
    mr.log("openings", mr.describe_openings(sh))
    sh.export(a.out)
    mr.log("wrote", f"{a.out}  {len(sh.faces):,} faces  {e[0]:.1f} x {e[1]:.1f} x {e[2]:.1f} mm  ({time.time() - t0:.1f} s)")

    if a.views:
        import subprocess
        png = a.out.rsplit(".", 1)[0] + "_views.png"
        subprocess.run([sys.executable, str(HERE / "mesh_views.py"), a.out, "--out", png, "--height", f"{e[2]:.2f}"], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
