#!/usr/bin/env python3
"""
mesh_repair.py — from ComfyUI output to something the slicer will accept.

    python tools/mesh_repair.py bear.glb --out bear_print.stl --height 160
    python tools/mesh_repair.py bear.glb --out bear_print.stl --height 160 --open-base \\
        --views bear_print_views.png

Reconstruction meshes (Hunyuan3D, TripoSR, ...) are marching-cubes surfaces
pulled from a noisy field: one big shell with hundreds of boundary loops,
self-intersections, a wildly wrong Euler number, and a cloud of tiny debris
shells. Hole filling cannot repair that class of defect. The boundary loops
are not holes in an otherwise good surface; they are where the surface
crosses itself and the extractor gave up, so any patch you sew across them
is itself non-manifold. The default here is a volumetric remesh instead:
rasterise the shell, fill it to a solid, and pull a fresh surface out with
marching cubes. That surface is watertight by construction, and manifold3d
is asked to agree before anything else happens to it.

Steps, in order, each one reported as it runs:

    orient      Y-up glTF onto its feet (see check_mesh.py --up)
    scale       uniform, to --height mm, so --pitch means millimetres of print
    component   keep the largest connected shell; everything else is debris
    remesh      --method voxel (default): voxelise at --pitch, close, flood-fill,
                marching cubes at --iso (0.7 undoes the half-pitch skin growth).
                meshfix: pymeshfix.  fill: trimesh fill_holes (kept so the failure
                is reproducible).  none: skip.
    validate    watertight, winding consistent, Euler number, manifold3d status
    smooth      --smooth N: Taubin, takes the voxel terracing out of the skin
    fill legs   --fill-legs hull|between: close the gap between the hind legs
                with a low block (manifold3d hull + union), so the crotch is not
                an overhang; a rock slab under the feet is left as it is
    decimate    quadric edge collapse to --faces (the low-poly look is the point)
    winding     outward normals, positive volume
    open base   --open-base: manifold3d boolean, subtract a box below --base mm
    place       centred on XY, feet on z=0

Then a before/after table and an STL. Exit code is check_mesh's: 0 if the
result is watertight with under 5% of its surface needing support.

--height is the printed height, what comes off the plate. With --open-base
the bear is scaled to --height plus --base before the cut, so the piece is
--height tall after it; the table shows both numbers. Without --height,
--pitch is in the file's own units and defaults to the same fraction of the
model as 0.6 mm is of a 160 mm print. A bare --views writes the sheet beside
the STL.

    pip install trimesh manifold3d numpy scipy scikit-image fast_simplification pymeshfix
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_mesh as cm  # noqa: E402

DEFAULT_FACES = 12000      # 6000 flattens the open jaw; 12000 keeps it readable
DEFAULT_BASE = 8.0
DEFAULT_SMOOTH = 10        # taubin iterations when --smooth is given bare
DEFAULT_PITCH = 0.6        # mm at print scale: about one nozzle width
DEFAULT_ISO = 0.5          # marching-cubes level; 0.7 cancels the half-pitch skin growth
REFERENCE_HEIGHT = 160.0   # the height DEFAULT_PITCH is quoted at
CLOSE_VOXELS = 2           # morphological closing radius before the flood fill
METHODS = ("voxel", "meshfix", "fill", "none")


def log(step, msg):
    print(f"  {step:<10} {msg}", flush=True)


# -------------------------------------------------------------- validate

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


def validate(mesh):
    """The four checks that decide whether a mesh is a solid, plus a body count."""
    return {
        "faces": len(mesh.faces),
        "bodies": int(mesh.body_count),
        "watertight": bool(mesh.is_watertight),
        "winding": bool(mesh.is_winding_consistent),
        "euler": int(mesh.euler_number),
        "manifold": manifold_status(mesh),
    }


def validation_line(v):
    return (f"watertight {str(v['watertight']).lower()}  winding {str(v['winding']).lower()}  "
            f"euler {v['euler']}  manifold3d {v['manifold']}  bodies {v['bodies']}")


def is_solid(v):
    return v["watertight"] and v["winding"] and v["manifold"] == "NoError"


def report(step, mesh):
    v = validate(mesh)
    log(step, validation_line(v))
    return v


# -------------------------------------------------------------- component

def largest_component(mesh):
    """Keep the biggest connected shell; the rest is marching-cubes confetti."""
    parts = mesh.split(only_watertight=False)
    if len(parts) <= 1:
        log("component", "one shell")
        return mesh
    parts = sorted(parts, key=lambda p: len(p.faces), reverse=True)
    log("component", f"kept the largest of {len(parts)} shells "
                     f"({len(parts[0].faces):,} faces), dropped {len(parts) - 1} debris "
                     f"(next largest {len(parts[1].faces):,} faces)")
    return parts[0]


# ----------------------------------------------------------------- remesh

def voxel_remesh(mesh, pitch, close=CLOSE_VOXELS, level=DEFAULT_ISO):
    """
    Give up on the surface and rebuild it from occupancy.

    Rasterise the shell at `pitch`, close small gaps morphologically, flood-fill
    the inside, smooth the occupancy field one voxel, and pull the `level`
    isosurface. If the flood fill leaks through a gap wider than the closing
    radius the interior stays empty; that is detected (interior smaller than
    the shell) and the closing radius widened. The result grows by about half
    a pitch of skin, because a voxel the surface passes through counts as
    solid; detail smaller than a pitch is gone, which decimation would have
    thrown away anyway. `level` 0.5 is that grown boundary; the field is a
    one-voxel Gaussian of the occupancy, so 0.7 pulls the surface half a
    voxel inward, back onto the original (measured: mean distance to the
    original 0.18 -> 0.05 mm at 0.4 mm pitch, thin features 0.4 mm slimmer).
    """
    from scipy import ndimage
    from skimage import measure

    t0 = time.time()
    grid = mesh.voxelized(pitch)
    shell = grid.matrix
    log("remesh", f"voxelised at {pitch:g} pitch: grid {'x'.join(map(str, shell.shape))}, "
                  f"{int(shell.sum()):,} shell voxels  ({time.time() - t0:.1f} s)")

    for radius in (close, close + 1, close + 3):
        pad = radius + 2
        S = np.pad(shell, pad)
        solid = ndimage.binary_dilation(S, iterations=radius)
        solid = ndimage.binary_fill_holes(solid)
        solid = ndimage.binary_erosion(solid, iterations=radius) | S
        interior = int((solid & ~S).sum())
        if interior >= S.sum():
            break
        log("remesh", f"closing radius {radius} did not seal the shell "
                      f"(interior {interior:,} < shell {int(S.sum()):,} voxels); widening")
    del S
    n_solid = int(solid.sum())
    log("remesh", f"filled to a solid: {n_solid:,} voxels, closing radius {radius}")

    field = ndimage.gaussian_filter(solid.astype(np.float32), sigma=1.0)
    del solid
    verts, faces, _, _ = measure.marching_cubes(field, level=level)
    del field
    verts = trimesh.transform_points(verts - pad, grid.transform)
    out = trimesh.Trimesh(verts, faces[:, ::-1], process=True)
    # where the isosurface passes exactly through a grid node, marching cubes
    # emits coincident vertices; merged, they leave zero-area faces whose
    # edges are shared 4 or 6 ways and the mesh is no longer watertight
    n = len(out.faces)
    out.update_faces(out.nondegenerate_faces())
    out.update_faces(out.unique_faces())
    out.remove_unreferenced_vertices()
    if len(out.faces) != n:
        log("remesh", f"dropped {n - len(out.faces)} zero-area/duplicate faces from marching cubes")
    if out.body_count > 1:
        parts = sorted(out.split(only_watertight=False), key=lambda p: len(p.faces), reverse=True)
        log("remesh", f"marching cubes produced {len(parts)} shells; kept the largest")
        out = parts[0]
    log("remesh", f"marching cubes at level {level:g}: {len(out.faces):,} faces  "
                  f"({time.time() - t0:.1f} s)")
    out.metadata["voxel"] = {"pitch": pitch, "level": level,
                             "grid": "x".join(map(str, shell.shape)),
                             "shell": int(shell.sum()), "solid": n_solid, "close": radius,
                             "seconds": time.time() - t0}
    return out


def meshfix_remesh(mesh, pitch=None):
    """MeshFix: removes self-intersections and fills what it can. Heuristic, but fast."""
    import pymeshfix
    t0 = time.time()
    fix = pymeshfix.MeshFix(np.asarray(mesh.vertices, np.float64),
                            np.asarray(mesh.faces, np.int32))
    fix.repair(joincomp=False, remove_smallest_components=True)
    out = trimesh.Trimesh(fix.points, fix.faces, process=True)
    log("remesh", f"pymeshfix: {len(out.faces):,} faces  ({time.time() - t0:.1f} s)")
    return out


def fill_remesh(mesh, pitch=None):
    """trimesh only patches 3- and 4-edge holes. Kept so the failure is reproducible."""
    t0 = time.time()
    before = len(mesh.outline().entities) if not mesh.is_watertight else 0
    trimesh.repair.fill_holes(mesh)
    after = len(mesh.outline().entities) if not mesh.is_watertight else 0
    log("remesh", f"trimesh fill_holes: boundary loops {before} -> {after}  "
                  f"({time.time() - t0:.1f} s)")
    return mesh


REMESH = {"voxel": voxel_remesh, "meshfix": meshfix_remesh, "fill": fill_remesh}


# -------------------------------------------------------------- fill legs

def slice_regions(mesh, z):
    """How many separate regions a horizontal slice at z has (0 if the plane misses)."""
    section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if section is None:
        return 0
    planar, _ = section.to_2D()
    return len(planar.polygons_full)


def leg_band(mesh, step=1.0, top_fraction=0.6):
    """
    (band_lo, crotch): the z range over which horizontal slices are two or
    more regions, scanning up from the plate. band_lo is the plate itself
    when the feet are already separate there, otherwise the top of whatever
    the bear stands on (a rock slab); crotch is the first slice above that
    which is one region again. None if the slices never split, or never
    rejoin below `top_fraction` of the height.
    """
    lo, hi = mesh.bounds[0][2], mesh.bounds[1][2]
    band_lo = None
    last_single = None
    z = lo + step / 2
    while z < lo + top_fraction * (hi - lo):
        n = slice_regions(mesh, z)
        if n >= 2 and band_lo is None:
            band_lo = lo if last_single is None else (last_single + z) / 2
        elif n == 1:
            if band_lo is not None:
                return band_lo, z
            last_single = z
        z += step
    return None


def to_manifold(mesh):
    import manifold3d as m3
    mm = m3.Mesh(vert_properties=np.ascontiguousarray(mesh.vertices, np.float32),
                 tri_verts=np.ascontiguousarray(mesh.faces, np.uint32))
    mm.merge()
    return m3.Manifold(mm)


def from_manifold(man, process=True):
    """
    Back to trimesh. Boolean output wants process=False: it carries sliver
    triangles whose vertices trimesh's merge would fuse into non-manifold
    edges, and it is already watertight as manifold3d hands it over.
    """
    mm = man.to_mesh()
    return trimesh.Trimesh(np.asarray(mm.vert_properties)[:, :3], np.asarray(mm.tri_verts),
                           process=process)


def largest_piece(man):
    """A boolean can leave zero-volume bubbles of a few triangles; keep the real body."""
    pieces = man.decompose()
    if len(pieces) <= 1:
        return man
    return max(pieces, key=lambda m: m.volume())


def fill_legs(mesh, variant="hull", margin=4.0, sink=4.0):
    """
    Fill the gap between the hind legs so the crotch stops being an overhang.

    The block is the convex hull of the leg band: every vertex from where the
    slices first split into two legs up to the crotch plus `margin` mm. When
    the bear stands on something (a rock slab) the band starts above it and
    the block is sunk `sink` mm into it, so the slab keeps its own shape
    instead of being hulled into a cone. Hulls and booleans are manifold3d's:
    qhull's hull of a 100k-point cloud came back non-watertight and the union
    refused it.

    hull:     union the bear with that block; reads as the bear standing in a
              low plinth.
    between:  the same block clipped to the vertical extrusion of the feet's
              footprint hull, so it cannot bulge in front of or behind the
              feet and only the gap between the legs is filled.
    """
    import manifold3d as m3
    t0 = time.time()
    band = leg_band(mesh)
    lo = mesh.bounds[0][2]
    if band is None:
        log("fill legs", "slices never split then rejoin below 60% height; nothing to fill")
        return mesh
    band_lo, crotch = band
    top = crotch + margin
    V = mesh.vertices
    pts = V[(V[:, 2] >= band_lo) & (V[:, 2] <= top)]
    sink = min(sink, band_lo - lo)          # 0 when the feet stand on the plate
    foot = mesh.section(plane_origin=[0, 0, band_lo + 1.0], plane_normal=[0, 0, 1]).vertices
    if sink > 0:
        sunk = foot.copy()
        sunk[:, 2] = band_lo - sink
        pts = np.vstack([pts, sunk])
    fill = m3.Manifold.hull_points(np.ascontiguousarray(pts, np.float64))
    if variant == "between":
        xy = foot[:, :2]
        prism = m3.Manifold.hull_points(np.ascontiguousarray(np.vstack([
            np.c_[xy, np.full(len(xy), band_lo - sink - 1.0)],
            np.c_[xy, np.full(len(xy), top + 1.0)]]), np.float64))
        fill = fill ^ prism
    before_vol = mesh.volume
    out = from_manifold(largest_piece(to_manifold(mesh) + fill), process=False)
    out.metadata["legs"] = {"variant": variant, "band_lo_mm": float(band_lo - lo),
                            "crotch_mm": float(crotch - lo), "top_mm": float(top - lo),
                            "sink_mm": float(sink),
                            "added_cm3": float((out.volume - before_vol) / 1000)}
    log("fill legs", f"{variant}: legs split from z {band_lo - lo:.0f} mm, crotch at z "
                     f"{crotch - lo:.0f} mm, block to z {top - lo:.0f} mm"
                     + (f", sunk {sink:g} mm into the base" if sink > 0 else "")
                     + f", +{(out.volume - before_vol) / 1000:.1f} cm^3  "
                     f"{validation_line(validate(out))}  ({time.time() - t0:.1f} s)")
    return out


# --------------------------------------------------------------- decimate

def manifold_simplify(mesh, faces, rounds=12):
    """
    manifold3d's tolerance-driven simplify, bisected onto a face target.

    Slower to aim than quadric collapse but the output is a solid by
    construction, which matters after a boolean has left sliver triangles
    that edge collapse turns into open edges. The output is taken without
    trimesh's vertex merge (process=False), which would fuse the slivers'
    vertices into non-manifold edges; only solids are candidates.
    """
    man = to_manifold(mesh)
    lo, hi = 0.005, float(mesh.extents.max()) / 20
    best = None
    for _ in range(rounds):
        tol = (lo * hi) ** 0.5
        out = from_manifold(largest_piece(man.simplify(tol)), process=False)
        n = len(out.faces)
        if is_solid(validate(out)) and (best is None
                                        or abs(n - faces) < abs(len(best[1].faces) - faces)):
            best = (tol, out)
        if abs(n - faces) < 0.05 * faces and best is not None and best[0] == tol:
            break
        lo, hi = (tol, hi) if n > faces else (lo, tol)
    return best if best is not None else (None, mesh)


def decimate(mesh, faces):
    """Quadric edge collapse; manifold3d simplify if that breaks the solid."""
    if len(mesh.faces) <= faces:
        log("decimate", f"{len(mesh.faces):,} faces already under {faces:,}")
        return mesh
    import fast_simplification
    before = len(mesh.faces)
    v, f = fast_simplification.simplify(
        np.asarray(mesh.vertices, np.float32), np.asarray(mesh.faces, np.int64),
        target_count=faces, agg=7)
    out = trimesh.Trimesh(v, f, process=True)
    out.update_faces(out.nondegenerate_faces())
    out.remove_unreferenced_vertices()
    if is_solid(validate(out)):
        log("decimate", f"{before:,} -> {len(out.faces):,} faces (quadric)")
        return out
    log("decimate", "quadric collapse broke the solid; using manifold3d simplify")
    tol, out = manifold_simplify(mesh, faces)
    if tol is not None:
        log("decimate", f"{before:,} -> {len(out.faces):,} faces (manifold3d, tolerance "
                        f"{tol:.3f})")
        return out
    log("decimate", "every pass broke the solid; keeping the dense mesh")
    return mesh


# --------------------------------------------------------- winding, scale

def fix_winding(mesh):
    trimesh.repair.fix_normals(mesh, multibody=True)
    if mesh.is_watertight and mesh.volume < 0:
        mesh.invert()
    log("winding", f"consistent {str(mesh.is_winding_consistent).lower()}, "
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
    """Boolean-subtract a box covering everything below `base` mm, leaving a flat opening."""
    lo, hi = mesh.bounds
    margin = 10.0
    box = trimesh.creation.box(extents=[hi[0] - lo[0] + 2 * margin,
                                        hi[1] - lo[1] + 2 * margin, base + margin])
    box.apply_translation([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2,
                           lo[2] + base - (base + margin) / 2])
    cut = trimesh.boolean.difference([mesh, box], engine="manifold")
    if cut is None or cut.is_empty:
        log("open base", "boolean produced nothing; base left closed")
        return mesh
    cut.apply_translation([0, 0, -cut.bounds[0][2]])
    log("open base", f"removed bottom {base:g} mm (manifold3d boolean); "
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

def table(before, after, openings, base=None):
    def row(label, a, b):
        print(f"  {label:<15}{a:>22}{b:>22}")

    def yn(flag, shout=False):
        if flag:
            return "yes"
        return "NO" if shout else "no"

    def vol(i):
        return f"{i['volume_cm3']:.1f} cm^3" if i["volume_cm3"] is not None else "n/a (open)"

    def fp(i):
        return f"{i['footprint'][0]:.1f} x {i['footprint'][1]:.1f} mm"

    print()
    row("", "before", "after")
    row("faces", f"{before['faces']:,}", f"{after['faces']:,}")
    row("bodies", f"{before['bodies']:,}", f"{after['bodies']:,}")
    row("watertight", yn(before["watertight"]), yn(after["watertight"], shout=True))
    row("winding ok", yn(before["winding_ok"]), yn(after["winding_ok"], shout=True))
    row("euler", f"{before['euler']}", f"{after['euler']}")
    row("manifold3d", before["manifold"], after["manifold"])
    row("volume", vol(before), vol(after))
    if base:
        row("bear scale", f"{before['height']:.1f} mm", f"{after['height'] + base:.1f} mm")
    row("printed height", f"{before['height']:.1f} mm", f"{after['height']:.1f} mm")
    row("footprint", fp(before), fp(after))
    row("needs support", f"{before['unsupported_pct']:.2f}%", f"{after['unsupported_pct']:.2f}%")
    row("base openings", "-", str(openings) if openings is not None else "-")
    if after["bands"]:
        print("\n  where (after):")
        for z0, z1, area, worst in after["bands"]:
            print(f"    z {z0:6.1f}-{z1:6.1f} mm   {area:7.1f} mm^2   worst {worst:4.1f} deg")


def measure_all(mesh, limit):
    """check_mesh's numbers plus the topology checks, one dict."""
    info = cm.measure(mesh, limit)
    v = validate(mesh)
    info.update(bodies=v["bodies"], euler=v["euler"], manifold=v["manifold"])
    return info


def default_pitch(mesh, height):
    if height:
        return DEFAULT_PITCH
    return float(mesh.extents[2]) * DEFAULT_PITCH / REFERENCE_HEIGHT


def smooth(mesh, iterations):
    """
    Taubin smoothing of the dense remeshed surface, before decimation.

    Takes the voxel terracing out of the skin without the shrinkage a plain
    Laplacian causes (lamb 0.5 / nu -0.53 is the classic pass-band pair).
    Topology is untouched, so the solid stays a solid; validated anyway.
    """
    if not iterations:
        return mesh
    t0 = time.time()
    trimesh.smoothing.filter_taubin(mesh, lamb=0.5, nu=-0.53, iterations=iterations)
    log("smooth", f"taubin x{iterations}  {validation_line(validate(mesh))}  "
                  f"({time.time() - t0:.1f} s)")
    return mesh


def solidify(path, height=None, base=None, up="auto", method="voxel", pitch=None,
             limit=cm.LIMIT_DEG, iso=DEFAULT_ISO):
    """
    Load, orient, scale, keep the largest shell, remesh, validate.

    Returns (dense solid, 'before' measurements, bear-scale height, pitch).
    This is the expensive half; finish() can be run on it more than once.
    """
    up = cm.guess_up(path, up)
    mesh = cm.load(path)
    print(f"\n{path}")
    log("orient", f"{up}-up" + (" -> rotated to z-up" if up == "y" else ", unchanged"))
    mesh.merge_vertices()
    cm.orient_z_up(mesh, up)

    # the "before" column: same orientation and target scale, none of the repair
    scale_and_place(mesh, height)
    before = measure_all(mesh, limit)
    log("before", validation_line(validate(mesh)))

    # --height is the printed height: with a base cut the bear itself is
    # scaled to height + base so the piece is exactly --height after the cut
    work_height = (height + base) if (height and base) else height
    if height:
        scale_and_place(mesh, work_height)
        log("scale", f"bear to {work_height:g} mm"
                     + (f" (printed height {height:g} mm after the {base:g} mm cut)"
                        if base else ""))
    pitch = pitch if pitch is not None else default_pitch(mesh, height)

    mesh = largest_component(mesh)
    if method == "voxel":
        mesh = voxel_remesh(mesh, pitch, level=iso)
    elif method != "none":
        mesh = REMESH[method](mesh, pitch)
    checks = report("validate", mesh)
    if not is_solid(checks):
        log("validate", f"NOT a solid after --method {method}; the numbers below are not "
                        "trustworthy (try --method voxel)")
    return mesh, before, work_height, pitch


def finish(mesh, before, work_height, out, faces=DEFAULT_FACES, base=None, smooth_iters=0,
           limit=cm.LIMIT_DEG, height=None, method="voxel", pitch=None, t0=None, legs=None):
    """Smooth, fill legs, decimate, fix winding, rescale, cut the base, report, write."""
    t0 = t0 or time.time()
    level = mesh.metadata.get("voxel", {}).get("level", DEFAULT_ISO)
    mesh = smooth(mesh.copy() if smooth_iters else mesh, smooth_iters)
    legs_info = None
    if legs:
        mesh = fill_legs(mesh, legs)
        legs_info = mesh.metadata.get("legs")
    mesh = decimate(mesh, faces)
    if legs_info:
        mesh.metadata["legs"] = legs_info
    mesh = fix_winding(mesh)
    # the remesh grows the skin by about half a pitch; put the height back exactly
    scale_and_place(mesh, work_height)

    openings = None
    if base:
        if is_solid(validate(mesh)):
            mesh = open_base(mesh, base)
            scale_and_place(mesh, None)
            report("validate", mesh)
            openings = len(base_openings(mesh))
        else:
            log("open base", "skipped: mesh is not a solid, manifold3d would refuse")

    after = measure_all(mesh, limit)
    table(before, after, openings, base)
    if height and base:
        print(f"\n  note: bear scaled to {work_height:g} mm so the piece is {height:g} mm "
              f"after the {base:g} mm cut; 'before' is the raw at {height:g} mm, "
              f"'after' footprint is the printed piece")

    if legs_info:
        mesh.metadata["legs"] = legs_info   # the base cut made a new mesh; carry it over
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(out)
    print(f"\nwrote {out}  ({time.time() - t0:.1f} s, method: {method}"
          + (f", pitch {pitch:g}, level {level:g}" if method == "voxel" else "")
          + (f", taubin x{smooth_iters}" if smooth_iters else "") + ")\n")
    return mesh, after, method


def repair(path, out, faces=DEFAULT_FACES, height=None, base=None, up="auto",
           method="voxel", pitch=None, limit=cm.LIMIT_DEG, smooth_iters=0, legs=None,
           iso=DEFAULT_ISO):
    t0 = time.time()
    mesh, before, work_height, pitch = solidify(path, height, base, up, method, pitch, limit,
                                                iso)
    return finish(mesh, before, work_height, out, faces, base, smooth_iters, limit,
                  height, method, pitch, t0, legs)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--out", required=True, help="STL to write")
    ap.add_argument("--method", choices=METHODS, default="voxel",
                    help="how to make it a solid (default voxel)")
    ap.add_argument("--pitch", type=float,
                    help=f"voxel size for --method voxel, in mm when --height is given "
                         f"(default {DEFAULT_PITCH:g})")
    ap.add_argument("--iso", type=float, default=DEFAULT_ISO, metavar="LEVEL",
                    help=f"marching-cubes level for --method voxel (default {DEFAULT_ISO:g}: "
                         f"the voxel boundary, half a pitch outside the surface; 0.7 puts "
                         f"it back on the surface)")
    ap.add_argument("--faces", type=int, default=DEFAULT_FACES,
                    help=f"decimation target (default {DEFAULT_FACES})")
    ap.add_argument("--height", type=float, help="final height in mm")
    ap.add_argument("--open-base", action="store_true",
                    help="cut the bottom --base mm off so the base is open")
    ap.add_argument("--base", type=float, default=DEFAULT_BASE,
                    help=f"how much to cut with --open-base, in mm (default {DEFAULT_BASE})")
    ap.add_argument("--up", choices=cm.UP_CHOICES, default="auto",
                    help="up axis in the file (auto: y for .glb/.gltf, else z)")
    ap.add_argument("--limit", type=float, default=cm.LIMIT_DEG,
                    help="overhang threshold in degrees")
    ap.add_argument("--smooth", type=int, nargs="?", const=DEFAULT_SMOOTH, default=0,
                    metavar="N",
                    help=f"Taubin-smooth the remeshed surface before decimation, N "
                         f"iterations (default {DEFAULT_SMOOTH} when the flag is given)")
    ap.add_argument("--fill-legs", choices=("hull", "between"), default=None,
                    help="fill the gap between the hind legs: hull = stand the bear in the "
                         "convex hull of everything below the crotch; between = that hull "
                         "clipped to the feet's footprint")
    ap.add_argument("--views", nargs="?", const="", metavar="PNG",
                    help="also render a six-view sheet of the result (default: "
                         "<out>_views.png beside the STL)")
    args = ap.parse_args()

    mesh, after, method = repair(args.path, args.out, args.faces, args.height,
                                 args.base if args.open_base else None, args.up,
                                 args.method, args.pitch, args.limit, args.smooth,
                                 args.fill_legs, args.iso)
    if args.views is not None:
        import mesh_views
        out = Path(args.out)
        views = args.views or out.with_name(out.stem + "_views.png")
        png, _, _ = mesh_views.render(str(out), views, up="z", limit=args.limit)
        print(f"wrote {png}\n")
    return 0 if (after["watertight"] and after["unsupported_pct"] < 5.0) else 1


if __name__ == "__main__":
    sys.exit(main())
