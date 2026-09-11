#!/usr/bin/env python3
"""
mesh_closeup.py — the head and shoulders of several meshes, full resolution, same camera.

    python tools/mesh_closeup.py hunyuan.glb trellis.glb --out closeup.png --height 160

mesh_views.py decimates to 60k faces before drawing, which is fine for "is it
a bear" but hides exactly the surface detail this sheet exists to compare.
Here nothing is decimated: every face whose centre sits in the top --zfrac of
the standing height is drawn, from the front and from a three-quarter view,
one row per mesh, all panels at the same scale and under the same key light.
The row label carries the face count inside the crop.
"""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_mesh as cm  # noqa: E402
import mesh_views as mv  # noqa: E402

VIEWS = [("front", -mv.Y), ("three-quarter", mv.three_quarter(40.0, 20.0)), ("left", -mv.X)]


def crop(mesh, zfrac):
    lo, hi = mesh.bounds
    zcut = lo[2] + (hi[2] - lo[2]) * (1.0 - zfrac)
    keep = mesh.triangles_center[:, 2] >= zcut
    return mesh.triangles[keep], mesh.face_normals[keep]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("meshes", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--height", type=float, default=160.0)
    ap.add_argument("--zfrac", type=float, default=0.42, help="fraction of the height, from the top, to keep")
    ap.add_argument("--labels", nargs="*", help="one row label per mesh (default: file name)")
    a = ap.parse_args()

    rows = []
    for i, p in enumerate(a.meshes):
        mesh = cm.prepare(cm.load(p), cm.guess_up(p, "auto"), a.height)
        tris, normals = crop(mesh, a.zfrac)
        label = a.labels[i] if a.labels and i < len(a.labels) else Path(p).name
        rows.append((label, tris, normals))

    # each row is centred on its own crop (generators place the bear differently in
    # XY) but every panel shares one radius so the rows are at the same scale
    centers, radius = [], 0.0
    for _, tris, _ in rows:
        pts = tris.reshape(-1, 3)
        lo, hi = pts.min(0), pts.max(0)
        c = (lo + hi) / 2
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
                            for z in (lo[2], hi[2])]) - c
        radius = max(radius, max(np.abs(corners @ mv.camera(t).T[:, :2]).max() for _, t in VIEWS))
        centers.append(c)
    radius *= 1.04

    fig, axes = plt.subplots(len(rows), len(VIEWS), figsize=(5.2 * len(VIEWS), 5.4 * len(rows)),
                             dpi=mv.DPI, facecolor=mv.BACKGROUND, squeeze=False)
    for r, (label, tris, normals) in enumerate(rows):
        center = centers[r]
        classes = np.zeros(len(tris), int)
        for c, (name, toward) in enumerate(VIEWS):
            ax = axes[r, c]
            basis = mv.camera(toward)
            P = np.einsum("ij,nkj->nki", basis, tris - center)
            order = np.argsort(P[:, :, 2].mean(axis=1))
            colors = mv.face_colors(normals, basis, classes)
            ax.set_facecolor(mv.BACKGROUND)
            ax.add_collection(PolyCollection(P[order][:, :, :2], facecolors=colors[order],
                                             edgecolors=colors[order], linewidths=0.15))
            ax.set_xlim(-radius, radius)
            ax.set_ylim(-radius, radius)
            ax.set_aspect("equal")
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_edgecolor("#dedbd2")
            if r == 0:
                ax.set_title(name, fontsize=12, color=mv.INK, pad=6)
            if c == 0:
                ax.set_ylabel(f"{label}\n{len(tris):,} faces in crop", fontsize=11, color=mv.INK)
    mv.draw_scale_bar(axes[0, 0], mv.nice_length(radius / 2), "mm", radius)
    fig.suptitle(f"head and shoulders, top {a.zfrac:.0%} of {a.height:g} mm, full mesh, no decimation",
                 fontsize=13, color=mv.INK, y=0.995)
    fig.subplots_adjust(left=0.05, right=0.99, top=0.94, bottom=0.02, wspace=0.05, hspace=0.08)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=mv.DPI, facecolor=mv.BACKGROUND)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
