#!/usr/bin/env python3
"""
mesh_repair.py — from ComfyUI output to something the slicer will accept.

    python tools/mesh_repair.py bear.glb --out bear_print.stl
    python tools/mesh_repair.py bear.glb --out bear_print.stl --faces 6000 --height 160 --open-base

Steps, in order, each one reported as it runs:

    orient      Y-up glTF onto its feet (see check_mesh.py --up)
    clean       merge vertices, drop duplicate/degenerate faces and debris shells
    watertight  trimesh fill_holes -> MeshFix -> voxel remesh; first one that
                closes the mesh wins, and manifold3d gets the final say
    decimate    quadric edge collapse to --faces (the low-poly look is the point)
    winding     consistent face orientation, outward normals
    scale       uniform, to --height mm, centred on the plate
    open base   optional: boolean-subtract everything below --base mm so the
                light and the pole have a way in (manifold3d)

Then a before/after table and an STL. Exit code is check_mesh's: 0 if the
result is watertight with under 5% of its surface needing support.

    pip install trimesh manifold3d numpy scipy scikit-image pymeshfix fast_simplification
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_mesh as cm  # noqa: E402

DEFAULT_FACES = 6000
DEFAULT_BASE = 8.0
DEBRIS_FRACTION = 0.01   # shells smaller than this share of the faces are noise
VOXELS = 200             # voxel remesh resolution along the longest axis


def log(step, msg):
    print(f"  {step:<11} {msg}")


def manifold_status(mesh):
    """manifold3d's opinion of the topology. 'NoError' is the bar for booleans."""
    try:
        import manifold3d as m3
    except ImportError:
        return "manifold3d not installed"
    mm = m3.Mesh(vert_properties=np.ascontiguousarray(mesh.vertices, np.float32),
                 tri_verts=np.ascontiguousarray(mesh.faces, np.uint32))
    mm.merge()
    return m3.Manifold(mm).status().name


def hole_count(mesh):
    return len(mesh.outline().entities) if not mesh.is_watertight else 0


# ----------------------------------------------------------------- clean

def clean(mesh):
    """Merge, dedupe, and drop the confetti that voxel-to-mesh leaves behind."""
    before = len(mesh.faces)
    mesh.merge_vertices()
    mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()

    parts = mesh.split(only_watertight=False)
    dropped = 0
    if len(parts) > 1:
        keep = [p for p in parts if len(p.faces) >= DEBRIS_FRACTION * len(mesh.faces)]
        dropped = len(parts) - len(keep)
        mesh = keep[0] if len(keep) == 1 else trimesh.util.concatenate(keep)
    log("clean", f"{before:,} -> {len(mesh.faces):,} faces"
                 + (f", dropped {dropped} debris shells" if dropped else ""))
    return mesh


# ------------------------------------------------------------ watertight

def try_fill_holes(mesh):
    """trimesh only patches 3- and 4-edge holes; cheap, so try it first."""
    trimesh.repair.fill_holes(mesh)
    return mesh


def try_meshfix(mesh):
    """MeshFix: fills arbitrary holes and removes self-intersections."""
    import pymeshfix
    fix = pymeshfix.MeshFix(np.asarray(mesh.vertices, np.float64),
                            np.asarray(mesh.faces, np.int32))
    fix.repair()
    return trimesh.Trimesh(fix.points, fix.faces, process=True)


def try_voxel_remesh(mesh, voxels=VOXELS, close=2):
    """
    Give up on the surface and rebuild it from occupancy.

    Rasterise the shell, close small gaps morphologically, flood-fill the
    inside, smooth, and pull an isosurface. Loses detail below one voxel
    (~1 mm at 160 mm tall) which decimation would have thrown away anyway.
    """
    from scipy import ndimage
    pitch = float(mesh.extents.max()) / voxels
    grid = mesh.voxelized(pitch)
    pad = close + 2
    shell = np.pad(grid.matrix, pad)
    solid = ndimage.binary_dilation(shell, iterations=close)
    solid = ndimage.binary_fill_holes(solid)
    solid = ndimage.binary_erosion(solid, iterations=close) | shell
    field = ndimage.gaussian_filter(solid.astype(np.float32), sigma=1.0)

    try:
        from skimage import measure
        verts, faces, _, _ = measure.marching_cubes(field, level=0.5)
        faces = faces[:, ::-1]
    except ImportError:
        verts, faces = level_set(field - 0.5)
    verts = trimesh.transform_points(verts - pad, grid.transform)
    return trimesh.Trimesh(verts, faces, process=True)


def level_set(field, edge=1.0):
    """manifold3d's marching tetrahedra over a grid, for when scikit-image is missing."""
    import manifold3d as m3
    sx, sy, sz = field.shape

    def sample(x, y, z):
        return float(field[int(min(max(x, 0), sx - 1)),
                           int(min(max(y, 0), sy - 1)),
                           int(min(max(z, 0), sz - 1))])

    man = m3.Manifold.level_set(sample, [0, 0, 0, sx - 1, sy - 1, sz - 1], edge, 0.0)
    mesh = man.to_mesh()
    return np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts)


LADDER = [("fill_holes", try_fill_holes), ("meshfix", try_meshfix),
          ("voxel remesh", try_voxel_remesh)]


def make_watertight(mesh, voxels=VOXELS):
    """Climb the ladder until something closes the mesh. Returns (mesh, method or None)."""
    if mesh.is_watertight:
        log("watertight", f"already closed (manifold3d: {manifold_status(mesh)})")
        return mesh, "none needed"
    for name, step in LADDER:
        t0 = time.time()
        try:
            candidate = (step(mesh.copy(), voxels) if step is try_voxel_remesh
                         else step(mesh.copy()))
        except ImportError as e:
            log("watertight", f"{name}: skipped, {e.name} not installed")
            continue
        except Exception as e:  # a failed repair is information, not a crash
            log("watertight", f"{name}: failed ({type(e).__name__}: {e})")
            continue
        if candidate.is_watertight and candidate.body_count >= 1:
            log("watertight", f"{name}: closed it, {len(candidate.faces):,} faces, "
                              f"manifold3d: {manifold_status(candidate)}  "
                              f"({time.time() - t0:.1f} s)  <-- used")
            return candidate, name
        log("watertight", f"{name}: still open, {hole_count(candidate)} holes  "
                          f"({time.time() - t0:.1f} s)")
    log("watertight", "nothing closed it; continuing with the open mesh")
    return mesh, None


# -------------------------------------------------------------- decimate

def decimate(mesh, faces):
    if len(mesh.faces) <= faces:
        log("decimate", f"{len(mesh.faces):,} faces already under {faces:,}")
        return mesh
    import fast_simplification
    before, was_closed = len(mesh.faces), mesh.is_watertight
    v, f = fast_simplification.simplify(
        np.asarray(mesh.vertices, np.float32), np.asarray(mesh.faces, np.int64),
        target_count=faces, agg=7)
    out = trimesh.Trimesh(v, f, process=True)
    out.update_faces(out.nondegenerate_faces())
    out.remove_unreferenced_vertices()
    note = ""
    if was_closed and not out.is_watertight:
        # edge collapse occasionally pinches; the cheap repairs fix it at this size
        for name, step in LADDER[:2]:
            try:
                fixed = step(out.copy())
            except Exception:
                continue
            if fixed.is_watertight:
                out, note = fixed, f", re-closed with {name}"
                break
        else:
            note = ", OPENED IT (check the result)"
    log("decimate", f"{before:,} -> {len(out.faces):,} faces (quadric){note}")
    return out


# --------------------------------------------------------- winding, scale

def fix_winding(mesh):
    trimesh.repair.fix_normals(mesh, multibody=True)
    if mesh.is_watertight and mesh.volume < 0:
        mesh.invert()
    log("winding", f"consistent {mesh.is_winding_consistent}, "
                   f"volume {'positive' if mesh.volume > 0 else 'NEGATIVE'}")
    return mesh


def scale_and_place(mesh, height):
    """Scale to height (if given), centre on XY, feet on z=0."""
    if height:
        mesh.apply_scale(height / mesh.extents[2])
    lo, hi = mesh.bounds
    mesh.apply_translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    return mesh


# -------------------------------------------------------------- open base

def open_base(mesh, base):
    """Cut everything below `base` mm off, leaving a flat opening where the feet were."""
    lo, hi = mesh.bounds
    status = manifold_status(mesh)
    if status == "NoError":
        margin = 10.0
        box = trimesh.creation.box(extents=[hi[0] - lo[0] + 2 * margin,
                                            hi[1] - lo[1] + 2 * margin, base + margin])
        box.apply_translation([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2,
                               lo[2] + base - (base + margin) / 2])
        cut = trimesh.boolean.difference([mesh, box], engine="manifold")
        method = "manifold3d boolean"
    else:
        cut = trimesh.intersections.slice_mesh_plane(
            mesh, plane_normal=[0, 0, 1], plane_origin=[0, 0, lo[2] + base], cap=True)
        method = f"plane slice with cap (manifold3d said {status})"
    if cut is None or cut.is_empty:
        log("open base", f"{method} produced nothing; base left closed")
        return mesh
    cut.apply_translation([0, 0, -cut.bounds[0][2]])
    log("open base", f"removed bottom {base:g} mm via {method}; "
                     f"{describe_openings(cut)}")
    return cut


def base_openings(mesh, eps=0.05):
    """Footprint (dx, dy) of each separate hole in the plate-side face."""
    section = mesh.section(plane_origin=[0, 0, mesh.bounds[0][2] + eps],
                           plane_normal=[0, 0, 1])
    if section is None:
        return []
    return [(float(np.ptp(loop[:, 0])), float(np.ptp(loop[:, 1])))
            for loop in section.discrete]


def describe_openings(mesh):
    openings = base_openings(mesh)
    if not openings:
        return "no opening at the base"
    sizes = ", ".join(f"{dx:.0f}x{dy:.0f}" for dx, dy in openings)
    return f"{len(openings)} opening{'s' if len(openings) != 1 else ''} at the base ({sizes} mm)"


# ----------------------------------------------------------------- report

def table(before, after, openings):
    def row(label, a, b):
        print(f"  {label:<15}{a:>22}{b:>22}")

    def vol(i):
        return f"{i['volume_cm3']:.1f} cm^3" if i["volume_cm3"] is not None else "n/a (open)"

    def fp(i):
        return f"{i['footprint'][0]:.1f} x {i['footprint'][1]:.1f} mm"

    print()
    row("", "before", "after")
    row("faces", f"{before['faces']:,}", f"{after['faces']:,}")
    row("watertight", "yes" if before["watertight"] else "no",
        "yes" if after["watertight"] else "NO")
    row("volume", vol(before), vol(after))
    row("height", f"{before['height']:.1f} mm", f"{after['height']:.1f} mm")
    row("footprint", fp(before), fp(after))
    row("needs support", f"{before['unsupported_pct']:.2f}%", f"{after['unsupported_pct']:.2f}%")
    row("base openings", "-", str(openings) if openings is not None else "-")
    if after["bands"]:
        print("\n  where (after):")
        for z0, z1, area, worst in after["bands"]:
            print(f"    z {z0:6.1f}-{z1:6.1f} mm   {area:7.1f} mm^2   worst {worst:4.1f} deg")


def repair(path, out, faces=DEFAULT_FACES, height=None, base=None, up="auto",
           voxels=VOXELS, limit=cm.LIMIT_DEG):
    t0 = time.time()
    up = cm.guess_up(path, up)
    raw = cm.load(path)
    print(f"\n{path}")
    log("orient", f"{up}-up" + (" -> rotated to z-up" if up == "y" else ", unchanged"))
    cm.orient_z_up(raw, up)

    # the "before" column: same orientation and scale, none of the repair
    before = cm.measure(cm.prepare(raw.copy(), "z", height), limit)

    mesh = clean(raw)
    mesh, method = make_watertight(mesh, voxels)
    mesh = decimate(mesh, faces)
    mesh = fix_winding(mesh)

    # cut first, then the target height is the height you get
    scale_and_place(mesh, (height + base) if (height and base) else height)
    if height:
        log("scale", f"to {height:g} mm" + (f" (+{base:g} mm to be cut off)" if base else ""))
    openings = None
    if base:
        mesh = open_base(mesh, base)
        scale_and_place(mesh, None)
        openings = len(base_openings(mesh))

    after = cm.measure(mesh, limit)
    table(before, after, openings)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(out)
    print(f"\nwrote {out}  ({time.time() - t0:.1f} s, watertight via: {method})\n")
    return mesh, after, method


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--out", required=True, help="STL to write")
    ap.add_argument("--faces", type=int, default=DEFAULT_FACES,
                    help=f"decimation target (default {DEFAULT_FACES})")
    ap.add_argument("--height", type=float, help="final height in mm")
    ap.add_argument("--open-base", action="store_true",
                    help=f"cut the bottom --base mm off so the base is open")
    ap.add_argument("--base", type=float, default=DEFAULT_BASE,
                    help=f"how much to cut with --open-base, in mm (default {DEFAULT_BASE})")
    ap.add_argument("--up", choices=cm.UP_CHOICES, default="auto",
                    help="up axis in the file (auto: y for .glb/.gltf, else z)")
    ap.add_argument("--voxels", type=int, default=VOXELS,
                    help=f"voxel remesh resolution if it comes to that (default {VOXELS})")
    ap.add_argument("--limit", type=float, default=cm.LIMIT_DEG,
                    help="overhang threshold in degrees")
    ap.add_argument("--views", help="also render a contact sheet of the result to this png")
    args = ap.parse_args()

    mesh, after, method = repair(args.path, args.out, args.faces, args.height,
                                 args.base if args.open_base else None, args.up,
                                 args.voxels, args.limit)
    if args.views:
        import mesh_views
        png, _, _ = mesh_views.render(args.out, args.views, up="z", limit=args.limit)
        print(f"wrote {png}\n")
    return 0 if (after["watertight"] and after["unsupported_pct"] < 5.0) else 1


if __name__ == "__main__":
    sys.exit(main())
