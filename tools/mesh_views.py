#!/usr/bin/env python3
"""
mesh_views.py — six views of a mesh on one sheet, no GPU, no window.

    python tools/mesh_views.py bear.glb --height 160
    python tools/mesh_views.py bear_print.stl --out bear_print_views.png

Front, left, back, right, top and a three-quarter view, orthographic, lit
from over the viewer's left shoulder, dark mesh on a light ground, all six
at the same scale. Faces that need support (downward, shallower than
--limit degrees, not resting on the plate) are tinted red so the sheet
shows where the support goes, not only how much. The footer carries the
check_mesh.py numbers, so one image answers "does it look like a bear" and
"will it print" together.

Views are named the way Blender names them. Front looks at the model's -Y
face (glTF's forward, once check_mesh has stood it up); left looks from -X,
right from +X; top looks down with the front at the bottom of the panel.
Walk the top row left to right and you walk around the bear.

Drawing is a painter's algorithm over matplotlib polygons. Meshes past
--render-faces are decimated for drawing only; the footer numbers always
come from the full mesh.

    pip install matplotlib fast_simplification
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_mesh as cm  # noqa: E402

RENDER_FACES = 60_000
DPI = 130

BACKGROUND = "#f4f3ee"
INK = "#2b2b2b"
PLATE = "#b9b6ad"
DARK = np.array([0.12, 0.13, 0.17])    # shadow side of the mesh
LIGHT = np.array([0.58, 0.60, 0.64])   # lit side; still darker than the ground
BAD_DARK = np.array([0.55, 0.10, 0.08])   # shadow side of a face that needs support
BAD_LIGHT = np.array([0.95, 0.40, 0.30])  # lit side of the same
KEY_LIGHT = np.array([-0.35, 0.50, 0.79])  # camera space: upper left, over the shoulder
KEY_LIGHT /= np.linalg.norm(KEY_LIGHT)

X, Y, Z = np.eye(3)


def camera(toward):
    """Right/up/toward basis for an orthographic camera at `toward`, looking at the origin."""
    v = np.asarray(toward, float)
    v = v / np.linalg.norm(v)
    up = Y if abs(v[2]) > 0.999 else Z   # top view: screen-up is +Y, so the front is at the bottom
    u = up - np.dot(up, v) * v
    u /= np.linalg.norm(u)
    return np.array([np.cross(u, v), u, v])


def three_quarter(az_deg=35.0, el_deg=25.0):
    """Camera direction rotated az degrees off the front toward +X and lifted el degrees."""
    az, el = np.radians(az_deg), np.radians(el_deg)
    return np.array([np.sin(az) * np.cos(el), -np.cos(az) * np.cos(el), np.sin(el)])


VIEWS = [
    ("front", -Y), ("left", -X), ("back", Y),
    ("right", X), ("top", Z), ("three-quarter", three_quarter()),
]


def for_drawing(mesh, max_faces=RENDER_FACES):
    """A lighter copy for the renderer; the silhouette survives, the time doesn't."""
    if len(mesh.faces) <= max_faces:
        return mesh
    try:
        import fast_simplification
    except ImportError:
        return mesh
    v, f = fast_simplification.simplify(
        np.asarray(mesh.vertices, np.float32), np.asarray(mesh.faces, np.int64),
        target_count=max_faces, agg=5)
    return trimesh.Trimesh(v, f, process=False)


def nice_length(target):
    """A round scale-bar length near target: 1, 2, 5 x 10^n."""
    mag = 10 ** np.floor(np.log10(target))
    return float(min((1, 2, 5), key=lambda m: abs(m * mag - target)) * mag)


def face_colors(normals, basis, bad):
    """Lambert shading in camera space; red ramp for faces that need support."""
    shade = np.abs((normals @ basis.T) @ KEY_LIGHT)[:, None]   # abs: don't punish bad winding
    colors = DARK + (LIGHT - DARK) * shade
    colors[bad] = BAD_DARK + (BAD_LIGHT - BAD_DARK) * shade[bad]
    return colors


def draw_panel(ax, tris, normals, bad, basis, center, radius, plate, title):
    P = np.einsum("ij,nkj->nki", basis, tris - center)      # camera-space triangles
    order = np.argsort(P[:, :, 2].mean(axis=1))              # far first
    colors = face_colors(normals, basis, bad)

    ax.set_facecolor(BACKGROUND)
    Q = (plate - center) @ basis.T
    ax.add_patch(plt.Polygon(Q[:, :2], closed=True, fill=False, ec=PLATE,
                             lw=0.8, ls="--", zorder=0))
    ax.add_collection(PolyCollection(
        P[order][:, :, :2], facecolors=colors[order], edgecolors=colors[order],
        linewidths=0.2, zorder=1))
    ax.set_xlim(-radius, radius)
    ax.set_ylim(-radius, radius)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor("#dedbd2")
    ax.set_title(title, fontsize=12, color=INK, pad=6)


def draw_scale_bar(ax, length, unit, radius):
    x0, y0 = -radius * 0.92, -radius * 0.92
    ax.plot([x0, x0 + length], [y0, y0], color=INK, lw=2, solid_capstyle="butt", zorder=2)
    ax.text(x0, y0 + radius * 0.03, f"{length:g} {unit}", fontsize=9, color=INK, va="bottom")


def footer_line(info):
    wt = "yes" if info["watertight"] else "NO"
    fx, fy = info["footprint"]
    band = info["worst_band"]
    where = (f"   worst band z {band[0]:.0f}-{band[1]:.0f} ({band[2]:.0f} mm^2)"
             if band else "")
    return (f"{info['faces']:,} tris   watertight {wt}   height {info['height']:.1f} mm   "
            f"footprint {fx:.1f} x {fy:.1f} mm   "
            f"needs support {info['unsupported_pct']:.1f}%{where}")


def guess_unit(path, height):
    """Scaled meshes and print-format files are in mm; a raw glTF is in whatever it likes."""
    if height or Path(path).suffix.lower() not in cm.Y_UP_SUFFIXES:
        return "mm"
    return "units"


def render(path, out=None, height=None, up="auto", render_faces=RENDER_FACES,
           limit=cm.LIMIT_DEG, unit=None):
    """Measure the full mesh, draw a decimated one. Returns (png path, measurements, up)."""
    up = cm.guess_up(path, up)
    mesh = cm.prepare(cm.load(path), up, height)
    info = cm.measure(mesh, limit)
    unit = unit or guess_unit(path, height)

    draw = for_drawing(mesh, render_faces)
    tris, normals = draw.triangles, draw.face_normals
    bad = cm.overhang_census(draw, limit)["mask"]
    lo, hi = mesh.bounds
    center = (lo + hi) / 2
    plate = np.array([[lo[0], lo[1], lo[2]], [hi[0], lo[1], lo[2]],
                      [hi[0], hi[1], lo[2]], [lo[0], hi[1], lo[2]]])
    corners = trimesh.bounds.corners(mesh.bounds) - center
    radius = max(np.abs(corners @ camera(t).T[:, :2]).max() for _, t in VIEWS) * 1.06

    fig, axes = plt.subplots(2, 3, figsize=(15, 10.6), dpi=DPI, facecolor=BACKGROUND)
    for ax, (name, toward) in zip(axes.flat, VIEWS):
        draw_panel(ax, tris, normals, bad, camera(toward), center, radius, plate, name)
    draw_scale_bar(axes[0, 0], nice_length(info["height"] / 4), unit, radius)

    fig.suptitle(Path(path).name, fontsize=15, color=INK, y=0.985)
    fig.text(0.5, 0.032, footer_line(info), ha="center", fontsize=11, color=INK,
             family="monospace")
    fig.text(0.5, 0.010, f"red: faces that need support (downward, shallower than "
                         f"{limit:g} deg, not on the plate)   dashed: build plate footprint",
             ha="center", fontsize=8.5, color="#6b6b6b")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=0.07,
                        wspace=0.06, hspace=0.14)

    out = Path(out) if out else Path(path).with_name(Path(path).stem + "_views.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=DPI, facecolor=BACKGROUND)
    plt.close(fig)
    return out, info, up


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--out", help="png to write (default: <mesh>_views.png beside it)")
    ap.add_argument("--height", type=float, help="scale to this height in mm first")
    ap.add_argument("--up", choices=cm.UP_CHOICES, default="auto",
                    help="up axis in the file (auto: y for .glb/.gltf, else z)")
    ap.add_argument("--render-faces", type=int, default=RENDER_FACES,
                    help=f"decimate to this many faces for drawing (default {RENDER_FACES})")
    ap.add_argument("--limit", type=float, default=cm.LIMIT_DEG,
                    help="overhang threshold in degrees for the tint and the footer")
    ap.add_argument("--unit", help="scale-bar unit label (default: mm, or 'units' for an "
                                   "unscaled glTF)")
    args = ap.parse_args()

    t0 = time.time()
    out, info, up = render(args.path, args.out, args.height, args.up,
                           args.render_faces, args.limit, args.unit)
    print(f"{args.path}  (up: {up})")
    print(f"  {footer_line(info)}")
    print(f"wrote {out}  ({time.time() - t0:.1f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
