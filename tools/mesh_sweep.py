#!/usr/bin/env python3
"""
mesh_sweep.py — quality sweeps over mesh_repair.py settings, CPU only.

    python tools/mesh_sweep.py grid outputs/stage2_mesh/round2z/c.glb --out outputs/stage3_print/quality/c \\
        --pitch 0.6 0.4 0.3 --faces 12000 25000 50000 --smooth 0 10
    python tools/mesh_sweep.py tilt outputs/stage2_mesh/round2z/c.glb --out outputs/stage3_print/quality/c \\
        --pitch 0.4 --faces 25000 --smooth 10
    python tools/mesh_sweep.py legs outputs/stage2_mesh/round2z/c.glb --out outputs/stage3_print/quality/c
    python tools/mesh_sweep.py thickness outputs/stage3_print/quality/c/c_p0.4_f25000_taubin.stl \\
        --out outputs/stage3_print/quality/c

grid       one cell per pitch x faces x smoothing: STL + six-view sheet + a row
           in grid.md / grid.json: solid?, tris, needs-support %, file size,
           wall time, fidelity. Fidelity is the distance from the repaired
           surface back to the original largest shell (mean and p95 over 20k
           samples, mm at print scale) plus p95 the other way round, which is
           what catches a filled mouth or a lost claw. The remesh is done once
           per pitch and shared by its six cells.
tilt       lean the repaired, closed bear about X (forward/back) and Y
           (sideways), re-cut the base at each orientation, record the
           needs-support % and the printed height.
legs       none / hull / between for mesh_repair's --fill-legs: support %
           before and after, the block's height and volume, a sheet each.
thickness  ray-cast local thickness on the printed piece: area fractions under
           2.5 mm and 4 mm, where they sit, the printed height that makes the
           ears 2.5 mm, and a sheet with thin faces coloured.

Every subcommand writes <out>/<name>.json and <name>.md so a run can be
resumed or read without re-running.
"""

import argparse
import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_mesh as cm  # noqa: E402
import mesh_repair as mr  # noqa: E402
import mesh_views as mv  # noqa: E402

HEIGHT = 160.0
BASE = 8.0
SAMPLES = 20_000
THIN, THINNISH = 2.5, 4.0     # mm: 2 walls of a 0.6 nozzle, and comfortable
RIM = 2.0                     # mm above the base cut ignored by the thickness census


def quiet(fn, *a, **k):
    """Run a chatty mesh_repair step without its log lines."""
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def cell_name(stem, pitch, faces, smooth, iso=mr.DEFAULT_ISO):
    return (f"{stem}_p{pitch:g}_f{faces}_{'taubin' if smooth else 'none'}"
            + (f"_iso{iso:g}" if iso != mr.DEFAULT_ISO else ""))


def original_shell(path, work_height, up="auto"):
    """The raw mesh's largest component at bear scale: the fidelity reference."""
    up = cm.guess_up(path, up)
    mesh = cm.load(path)
    mesh.merge_vertices()
    cm.orient_z_up(mesh, up)
    mr.scale_and_place(mesh, work_height)
    return quiet(mr.largest_component, mesh)


def fidelity(repaired, original, n=SAMPLES, seed=0):
    """Surface-to-surface distances in mm, both directions."""
    pts, _ = trimesh.sample.sample_surface(repaired, n, seed=seed)
    _, d1, _ = trimesh.proximity.closest_point(original, pts)
    pts2, _ = trimesh.sample.sample_surface(original, n, seed=seed)
    _, d2, _ = trimesh.proximity.closest_point(repaired, pts2)
    return {"mean": float(d1.mean()), "p95": float(np.percentile(d1, 95)),
            "max": float(d1.max()),
            "rev_mean": float(d2.mean()), "rev_p95": float(np.percentile(d2, 95)),
            "rev_max": float(d2.max())}


def cut_base(closed, base=BASE):
    """Open the base of a closed bear and set the piece on the plate."""
    piece = quiet(mr.open_base, closed, base)
    mr.scale_and_place(piece, None)
    return piece


def dump(out, name, rows, md):
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    (out / f"{name}.md").write_text(md, encoding="utf-8")


# ------------------------------------------------------------------- grid

def grid_md(stem, rows, remesh):
    lines = [f"## {stem}: surface quality grid", "",
             f"Printed height {HEIGHT:g} mm, base cut {BASE:g} mm. Fidelity is mm at print "
             f"scale over {SAMPLES:,} samples; 'back' is repaired->original, 'fwd' is "
             f"original->repaired (large fwd p95 = lost detail).", ""]
    if remesh:
        lines.append("| pitch | grid | solid voxels | dense tris | remesh s |")
        lines.append("|---:|---|---:|---:|---:|")
        for p, r in sorted(remesh.items(), key=lambda kv: -float(kv[0].split("@")[0])):
            lines.append(f"| {p} | {r['grid']} | {r['voxels']:,} | {r['faces']:,} | {r['seconds']:.0f} |")
        lines.append("")
    lines.append("| cell | solid | tris | support % | back mean | back p95 | fwd p95 | KB | wall s |")
    lines.append("|---|:---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        f = r["fidelity"]
        lines.append(f"| `{r['name']}` | {'yes' if r['solid'] else '**NO**'} | {r['tris']:,} "
                     f"| {r['support_pct']:.2f} | {f['mean']:.3f} | {f['p95']:.3f} | {f['rev_p95']:.3f} "
                     f"| {r['kb']:,} | {r['wall_s']:.0f} |")
    return "\n".join(lines) + "\n"


def run_grid(args):
    path, out = Path(args.path), Path(args.out)
    stem = path.stem
    out.mkdir(parents=True, exist_ok=True)
    rows, remesh = [], {}
    done = {}
    if (out / "grid.json").exists() and not args.fresh:
        prev = json.loads((out / "grid.json").read_text())
        rows = prev.get("rows", [])
        remesh = prev.get("remesh", {})
        done = {r["name"]: r for r in rows}

    for pitch in args.pitch:
        todo = [(f, s) for f in args.faces for s in args.smooth
                if cell_name(stem, pitch, f, s, args.iso) not in done]
        if not todo:
            print(f"pitch {pitch}: all cells done", flush=True)
            continue
        t0 = time.time()
        dense, before, work_height, _ = mr.solidify(str(path), HEIGHT, BASE, "auto",
                                                     "voxel", pitch, args.limit, args.iso)
        t_remesh = time.time() - t0
        vox = dense.metadata.get("voxel", {})
        remesh[f"{pitch:g}" + (f"@{args.iso:g}" if args.iso != mr.DEFAULT_ISO else "")] = {
                              "faces": len(dense.faces), "seconds": t_remesh, "iso": args.iso,
                              "grid": vox.get("grid", ""), "voxels": vox.get("solid", 0)}
        shell = original_shell(str(path), work_height)
        print(f"pitch {pitch}: remesh {t_remesh:.0f} s, {len(dense.faces):,} faces; "
              f"reference shell {len(shell.faces):,} faces", flush=True)

        for faces, smooth in todo:
            name = cell_name(stem, pitch, faces, smooth, args.iso)
            stl = out / f"{name}.stl"
            t1 = time.time()
            closed, _, _ = quiet(mr.finish, dense, before, work_height, stl, faces, None,
                                 smooth, args.limit, HEIGHT, "voxel", pitch)
            fid = fidelity(closed, shell)
            piece = cut_base(closed)
            v = mr.validate(piece)
            info = cm.measure(piece, args.limit)
            piece.export(stl)
            wall = t_remesh + (time.time() - t1)
            png, _, _ = mv.render(str(stl), out / f"{name}_views.png", height=HEIGHT,
                                  up="z", limit=args.limit)
            row = {"name": name, "pitch": pitch, "faces": faces, "smooth": smooth,
                   "iso": args.iso,
                   "solid": mr.is_solid(v), "tris": len(piece.faces),
                   "support_pct": info["unsupported_pct"],
                   "worst_band": info["worst_band"], "height": info["height"],
                   "footprint": info["footprint"], "fidelity": fid,
                   "kb": os.path.getsize(stl) // 1024, "wall_s": wall,
                   "stl": str(stl), "png": str(png)}
            rows.append(row)
            done[name] = row
            print(f"  {name:<32} solid {'yes' if row['solid'] else 'NO '}  {row['tris']:>7,} tris  "
                  f"support {row['support_pct']:5.2f}%  back {fid['mean']:.3f}/{fid['p95']:.3f}  "
                  f"fwd p95 {fid['rev_p95']:.3f}  {row['kb']:>5,} KB  {wall:4.0f} s", flush=True)
            rows.sort(key=lambda r: (-r["pitch"], r.get("iso", 0.5), r["faces"], r["smooth"]))
            dump(out, "grid", {"rows": rows, "remesh": remesh}, grid_md(stem, rows, remesh))
        del dense, shell
    print(f"wrote {out / 'grid.md'}")


# ------------------------------------------------------------------- tilt

def rotation(rx_deg, ry_deg):
    rx = trimesh.transformations.rotation_matrix(np.radians(rx_deg), [1, 0, 0])
    ry = trimesh.transformations.rotation_matrix(np.radians(ry_deg), [0, 1, 0])
    return ry @ rx


def tilt_md(stem, rows, setting):
    by = {(r["rx"], r["ry"]): r for r in rows}
    up = by[(0, 0)]
    best = min(rows, key=lambda r: r["support_pct"])
    steps = sorted({r["rx"] for r in rows})
    lines = [f"## {stem}: orientation sweep ({setting})", "",
             "Rotation about X: + leans forward (face down), - leans back. Rotation about "
             "Y: + leans to the viewer's right in the front view. Base re-cut 8 mm at each "
             "orientation; support % of the printed piece.", "",
             "| rx \\ ry | " + " | ".join(f"{s:+d}°" for s in steps) + " |",
             "|---:|" + "---:|" * len(steps)]
    for rx in steps:
        cells = []
        for ry in steps:
            r = by.get((rx, ry))
            s = f"{r['support_pct']:.2f}" if r else "-"
            if r and (rx, ry) == (best["rx"], best["ry"]):
                s = f"**{s}**"
            cells.append(s)
        lines.append(f"| {rx:+d}° | " + " | ".join(cells) + " |")
    lines += ["", f"Upright: {up['support_pct']:.2f} %. Best: rx {best['rx']:+d}°, ry "
                  f"{best['ry']:+d}° at {best['support_pct']:.2f} % "
                  f"({up['support_pct'] - best['support_pct']:.2f} points saved), printed "
                  f"height {best['height']:.1f} mm, footprint {best['footprint'][0]:.0f} x "
                  f"{best['footprint'][1]:.0f} mm.", ""]
    within = [r for r in rows if abs(r["rx"]) <= 10 and abs(r["ry"]) <= 10]
    b10 = min(within, key=lambda r: r["support_pct"])
    lines.append(f"Best within ±10°: rx {b10['rx']:+d}°, ry {b10['ry']:+d}° at "
                 f"{b10['support_pct']:.2f} %.")
    return "\n".join(lines) + "\n"


def run_tilt(args):
    path, out = Path(args.path), Path(args.out)
    stem = path.stem
    setting = f"pitch {args.pitch:g}, iso {args.iso:g}, {args.faces} faces, taubin x{args.smooth}"
    dense, before, work_height, _ = mr.solidify(str(path), HEIGHT, BASE, "auto",
                                                 "voxel", args.pitch, args.limit, args.iso)
    closed_stl = out / f"{stem}_closed.stl"
    closed, _, _ = quiet(mr.finish, dense, before, work_height, closed_stl, args.faces, None,
                         args.smooth, args.limit, HEIGHT, "voxel", args.pitch)
    del dense
    steps = list(range(-args.max_deg, args.max_deg + 1, args.step))
    rows = []
    for rx in steps:
        for ry in steps:
            m = closed.copy()
            m.apply_transform(rotation(rx, ry))
            piece = cut_base(m)
            v = mr.validate(piece)
            info = cm.measure(piece, args.limit)
            rows.append({"rx": rx, "ry": ry, "support_pct": info["unsupported_pct"],
                         "solid": mr.is_solid(v), "height": info["height"],
                         "footprint": info["footprint"], "worst_band": info["worst_band"]})
            print(f"  rx {rx:+3d}  ry {ry:+3d}  support {info['unsupported_pct']:5.2f}%  "
                  f"height {info['height']:.1f}  solid {'yes' if rows[-1]['solid'] else 'NO'}",
                  flush=True)
    best = min(rows, key=lambda r: r["support_pct"])
    m = closed.copy()
    m.apply_transform(rotation(best["rx"], best["ry"]))
    piece = cut_base(m)
    stl = out / f"{stem}_tilt_rx{best['rx']:+d}_ry{best['ry']:+d}.stl"
    piece.export(stl)
    mv.render(str(stl), out / f"{stem}_tilt_best_views.png", height=None, up="z",
              limit=args.limit)
    dump(out, "tilt", {"setting": setting, "rows": rows, "best": best},
         tilt_md(stem, rows, setting))
    print(f"wrote {out / 'tilt.md'}")


# ------------------------------------------------------------------- legs

def legs_md(stem, rows, setting):
    up = rows[0]
    lines = [f"## {stem}: filling the gap between the hind legs ({setting})", "",
             "`hull` stands the bear in the convex hull of the leg band (from where the "
             "slices split into two legs up to the crotch + 4 mm, sunk 4 mm into a slab if "
             "there is one); `between` clips that hull to the feet's footprint so only the "
             "gap itself is filled. Support % of the printed piece.", "",
             "| variant | solid | legs from z | crotch z | block to z | sunk | added cm³ | "
             "tris | support % | saved | worst band |",
             "|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        b = r["worst_band"]
        band = f"z {b[0]:.0f}-{b[1]:.0f} ({b[2]:.0f} mm²)" if b else "-"
        info = r.get("legs") or {}
        if info:
            geo = (f"{info['band_lo_mm']:.0f} | {info['crotch_mm']:.0f} | {info['top_mm']:.0f} "
                   f"| {info['sink_mm']:g} | {info['added_cm3']:.1f}")
        else:
            geo = "- | - | - | - | 0.0"
        lines.append(f"| {r['variant']} | {'yes' if r['solid'] else '**NO**'} | {geo} "
                     f"| {r['tris']:,} | {r['support_pct']:.2f} "
                     f"| {up['support_pct'] - r['support_pct']:.2f} | {band} |")
    return "\n".join(lines) + "\n"


def run_legs(args):
    path, out = Path(args.path), Path(args.out)
    stem = path.stem
    setting = f"pitch {args.pitch:g}, iso {args.iso:g}, {args.faces} faces, taubin x{args.smooth}"
    dense, before, work_height, _ = mr.solidify(str(path), HEIGHT, BASE, "auto",
                                                 "voxel", args.pitch, args.limit, args.iso)
    rows = []
    for variant in (None, "hull", "between"):
        name = f"{stem}_legs_{variant or 'none'}"
        stl = out / f"{name}.stl"
        t0 = time.time()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            piece, after, _ = mr.finish(dense, before, work_height, stl, args.faces, BASE,
                                        args.smooth, args.limit, HEIGHT, "voxel", args.pitch,
                                        None, variant)
        v = mr.validate(piece)
        png, _, _ = mv.render(str(stl), out / f"{name}_views.png", height=HEIGHT, up="z",
                              limit=args.limit)
        rows.append({"variant": variant or "none", "solid": mr.is_solid(v),
                     "tris": len(piece.faces), "support_pct": after["unsupported_pct"],
                     "worst_band": after["worst_band"], "volume_cm3": after["volume_cm3"],
                     "legs": piece.metadata.get("legs"), "seconds": time.time() - t0,
                     "stl": str(stl), "png": str(png)})
        note = [l.strip() for l in buf.getvalue().splitlines() if "fill legs" in l]
        print(f"  {name:<20} solid {'yes' if rows[-1]['solid'] else 'NO '}  "
              f"support {after['unsupported_pct']:5.2f}%  {rows[-1]['tris']:>7,} tris  "
              f"({time.time() - t0:.0f} s)  {note[0] if note else ''}", flush=True)
    dump(out, "legs", {"setting": setting, "rows": rows}, legs_md(stem, rows, setting))
    print(f"wrote {out / 'legs.md'}")


# -------------------------------------------------------------- thickness

def local_thickness(mesh, n=SAMPLES, seed=0):
    """Inward ray thickness at n area-uniform surface samples. Returns (points, face ids, mm)."""
    pts, fid = trimesh.sample.sample_surface(mesh, n, seed=seed)
    normals = mesh.face_normals[fid]
    thick = trimesh.proximity.thickness(mesh, pts, normals=normals, method="ray")
    thick = np.asarray(thick, float)
    thick[~np.isfinite(thick)] = np.inf     # rays that never hit: the far wall is far
    return pts, fid, thick


def face_classes(mesh, pts, fid, thick):
    """Per-face class: 1 under THIN, 2 under THINNISH, 0 otherwise. Unsampled faces borrow."""
    from scipy.spatial import cKDTree
    per_face = np.full(len(mesh.faces), np.inf)
    np.minimum.at(per_face, fid, thick)
    missing = ~np.isfinite(per_face) | (np.bincount(fid, minlength=len(mesh.faces)) == 0)
    if missing.any():
        _, idx = cKDTree(pts).query(mesh.triangles_center[missing])
        per_face[missing] = thick[idx]
    classes = np.zeros(len(mesh.faces), int)
    classes[per_face < THINNISH] = 2
    classes[per_face < THIN] = 1
    return classes, per_face


def where(mesh, pts, thick, limit, bands=6):
    """Area share of thin surface by height band."""
    lo, hi = mesh.bounds[0][2], mesh.bounds[1][2]
    edges = np.linspace(lo, hi, bands + 1)
    out = []
    thin = thick < limit
    for i in range(bands):
        sel = (pts[:, 2] >= edges[i]) & (pts[:, 2] < edges[i + 1] + 1e-9)
        if (sel & thin).any():
            out.append((float(edges[i]), float(edges[i + 1]),
                        100.0 * float((sel & thin).sum()) / len(pts),
                        float(np.median(thick[sel & thin]))))
    return out


def thin_spots(mesh, pts, thick, share=0.02, radius=6.0, min_points=15, top=8):
    """
    Where the thinnest `share` of the surface is: the thinnest samples
    clustered by proximity, each cluster as (centre xyz, min, median, count).
    Sorted thinnest first. Positions are relative to the model: z from the
    plate, x + is the viewer's right in the front view, y - is the front.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree
    ok = np.isfinite(thick)
    k = max(min_points, int(share * ok.sum()))
    idx = np.argsort(np.where(ok, thick, np.inf))[:k]
    P, T = pts[idx], thick[idx]
    pairs = cKDTree(P).query_pairs(radius, output_type="ndarray")
    graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(P), len(P)))
    _, labels = connected_components(graph, directed=False)
    lo = mesh.bounds[0]
    out = []
    for lab in np.unique(labels):
        sel = labels == lab
        if sel.sum() < min_points:
            continue
        c = np.median(P[sel], axis=0)
        out.append({"x": float(c[0]), "y": float(c[1]), "z": float(c[2] - lo[2]),
                    "min": float(T[sel].min()), "median": float(np.median(T[sel])),
                    "points": int(sel.sum())})
    out.sort(key=lambda r: r["min"])
    return out[:top]


def describe_spot(r, extents):
    """A plain-words position: height, side and front/back, from the numbers."""
    w, d = extents[0], extents[1]
    side = "centre" if abs(r["x"]) < 0.15 * w else ("viewer's right" if r["x"] > 0 else "viewer's left")
    fb = "middle" if abs(r["y"]) < 0.15 * d else ("front" if r["y"] < 0 else "back")
    return f"z {r['z']:.0f} mm, {side}, {fb}"


def run_thickness(args):
    path, out = Path(args.path), Path(args.out)
    stem = Path(args.path).stem
    mesh = cm.prepare(cm.load(str(path)), "z", None)
    t0 = time.time()
    pts, fid, thick = local_thickness(mesh, args.samples)
    height = float(mesh.extents[2])
    # the rim where the base cut meets the feet is a wedge the first layers
    # fill anyway; it is not a thin feature, so it is left out of the census
    rim = pts[:, 2] < mesh.bounds[0][2] + RIM
    rim_pct = 100.0 * float((rim & (thick < THIN)).mean())
    thick = np.where(rim, np.inf, thick)
    frac_thin = 100.0 * float((thick < THIN).mean())
    frac_thinnish = 100.0 * float((thick < THINNISH).mean())
    # ears: thin material in the top tenth of the model, near the head's axis
    # (raised paws sit at the same height but well out to the sides)
    top = pts[:, 2] > mesh.bounds[0][2] + 0.90 * height
    axis = np.median(pts[top][:, :2], axis=0) if top.any() else np.zeros(2)
    near = np.linalg.norm(pts[:, :2] - axis, axis=1) < 0.3 * float(mesh.extents[:2].max())
    ear = top & near & (thick < THINNISH * 2)
    ear_p10 = float(np.percentile(thick[ear], 10)) if ear.any() else float("nan")
    ear_med = float(np.median(thick[ear])) if ear.any() else float("nan")
    min_height = height * THIN / ear_p10 if ear.any() else float("nan")
    classes, per_face = face_classes(mesh, pts, fid, thick)
    footer = (f"{len(mesh.faces):,} tris   height {height:.1f} mm   "
              f"under {THIN:g} mm: {frac_thin:.1f}% of surface   under {THINNISH:g} mm: "
              f"{frac_thinnish:.1f}%   ears p10 {ear_p10:.1f} mm")
    png = out / f"{stem}_thickness_views.png"
    mv.render_mesh(mesh, png, title=f"{path.name}: local thickness", footer=footer,
                   legend=f"red: thinner than {THIN:g} mm (2 walls of a 0.6 nozzle)   "
                          f"orange: {THIN:g}-{THINNISH:g} mm   dashed: build plate",
                   classes=classes, palette={1: mv.RED, 2: mv.ORANGE}, unit="mm")
    bands_thin = where(mesh, pts, thick, THIN)
    bands_thinnish = where(mesh, pts, thick, THINNISH)
    spots = thin_spots(mesh, pts, thick)
    rows = {"stl": str(path), "height": height, "samples": int(len(pts)),
            "pct_under_2p5": frac_thin, "pct_under_4": frac_thinnish,
            "cut_rim_pct_under_2p5": rim_pct,
            "ear_p10": ear_p10, "ear_median": ear_med, "min_height_for_2p5_ears": min_height,
            "bands_under_2p5": bands_thin, "bands_under_4": bands_thinnish,
            "thin_spots": spots,
            "png": str(png), "seconds": time.time() - t0}
    lines = [f"## {stem}: thin-feature census ({path.name}, {height:.0f} mm printed)", "",
             f"| under {THIN:g} mm | under {THINNISH:g} mm | ears p10 | ears median | "
             f"height for {THIN:g} mm ears |", "|---:|---:|---:|---:|---:|",
             f"| {frac_thin:.1f} % of surface | {frac_thinnish:.1f} % | {ear_p10:.1f} mm | "
             f"{ear_med:.1f} mm | {min_height:.0f} mm |", "",
             f"The wedge rim within {RIM:g} mm of the base cut is left out ({rim_pct:.1f} % of "
             f"the surface is under {THIN:g} mm there; the first layers fill it).", "",
             f"Where (share of total surface, by height band): under {THIN:g} mm", ""]
    lines += [f"- z {a:.0f}-{b:.0f} mm: {s:.1f} % (median {m:.1f} mm)" for a, b, s, m in bands_thin]
    lines += ["", f"under {THINNISH:g} mm", ""]
    lines += [f"- z {a:.0f}-{b:.0f} mm: {s:.1f} % (median {m:.1f} mm)" for a, b, s, m in bands_thinnish]
    lines += ["", "Thinnest spots (the thinnest 2 % of samples, clustered within 6 mm; "
              "x + is the viewer's right in the front view, y - is the front):", "",
              "| where | x | y | min mm | median mm | samples |", "|---|---:|---:|---:|---:|---:|"]
    lines += [f"| {describe_spot(r, mesh.extents)} | {r['x']:.0f} | {r['y']:.0f} | {r['min']:.1f} "
              f"| {r['median']:.1f} | {r['points']} |" for r in spots]
    lines += ["", f"Sheet: `{png.name}`", ""]
    dump(out, "thickness", rows, "\n".join(lines))
    print("\n".join(lines))
    print(f"wrote {out / 'thickness.md'}  ({time.time() - t0:.0f} s)")


# ------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grid", help="pitch x faces x smoothing")
    g.add_argument("path")
    g.add_argument("--out", required=True)
    g.add_argument("--pitch", type=float, nargs="+", default=[0.6, 0.4, 0.3])
    g.add_argument("--faces", type=int, nargs="+", default=[12000, 25000, 50000])
    g.add_argument("--smooth", type=int, nargs="+", default=[0, 10])
    g.add_argument("--limit", type=float, default=cm.LIMIT_DEG)
    g.add_argument("--iso", type=float, default=mr.DEFAULT_ISO,
                   help="marching-cubes level (0.5 = voxel boundary, 0.7 = on the surface)")
    g.add_argument("--fresh", action="store_true", help="ignore an existing grid.json")
    g.set_defaults(fn=run_grid)

    t = sub.add_parser("tilt", help="lean about X and Y, re-cut the base")
    t.add_argument("path")
    t.add_argument("--out", required=True)
    t.add_argument("--pitch", type=float, default=0.4)
    t.add_argument("--faces", type=int, default=25000)
    t.add_argument("--smooth", type=int, default=10)
    t.add_argument("--max-deg", type=int, default=15)
    t.add_argument("--step", type=int, default=5)
    t.add_argument("--limit", type=float, default=cm.LIMIT_DEG)
    t.add_argument("--iso", type=float, default=mr.DEFAULT_ISO,
                   help="marching-cubes level (0.5 = voxel boundary, 0.7 = on the surface)")
    t.set_defaults(fn=run_tilt)

    lg = sub.add_parser("legs", help="fill the gap between the hind legs: none / hull / between")
    lg.add_argument("path")
    lg.add_argument("--out", required=True)
    lg.add_argument("--pitch", type=float, default=0.4)
    lg.add_argument("--faces", type=int, default=25000)
    lg.add_argument("--smooth", type=int, default=10)
    lg.add_argument("--limit", type=float, default=cm.LIMIT_DEG)
    lg.add_argument("--iso", type=float, default=mr.DEFAULT_ISO,
                   help="marching-cubes level (0.5 = voxel boundary, 0.7 = on the surface)")
    lg.set_defaults(fn=run_legs)

    k = sub.add_parser("thickness", help="local thickness census of a printed STL")
    k.add_argument("path")
    k.add_argument("--out", required=True)
    k.add_argument("--samples", type=int, default=SAMPLES)
    k.set_defaults(fn=run_thickness)

    args = ap.parse_args()
    args.fn(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
