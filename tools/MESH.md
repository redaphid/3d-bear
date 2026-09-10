# Stage 3 mesh tooling

Three scripts in `tools/` plus `check_mesh.py` at the repo root. All of them
are CPU-only (numpy, trimesh 4.12, manifold3d, scipy, scikit-image,
fast_simplification, pymeshfix, matplotlib); nothing needs a GPU or a window.

## What comes out of Hunyuan3D, and why hole-filling cannot fix it

`outputs/scratch/mesh_round1_d.glb` (Hunyuan3D 2.1, octree 256) measured at
160 mm tall:

| | raw GLB |
|---|---|
| triangles | 271,556 |
| connected shells | 874 (one body of 267,738 faces + 873 debris shells of ≤ 12 faces) |
| boundary loops on the body | 189 |
| Euler number | 349 (body alone: −178) |
| watertight / winding consistent | no / no |
| manifold3d | NotManifold |

That is marching-cubes output from a noisy field. The boundary loops are not
holes in an otherwise good surface. They sit where the surface crosses
itself and the extractor gave up, so the loops border self-intersecting,
non-manifold geometry. Sewing a patch across such a loop produces another
non-manifold patch; the mesh cannot become a solid that way. Measured:
`trimesh.repair.fill_holes` leaves all 189 loops in place (`--method fill`
reproduces this), and it only patches 3- and 4-edge holes in the first place.

The fix is volumetric. Rasterise the shell into a voxel grid, close small
gaps morphologically, flood-fill the interior to a solid, and pull a fresh
surface out with marching cubes over the smoothed occupancy field. A
marching-cubes isosurface of a padded scalar field is closed and manifold by
construction, with one caveat the tool handles: where the surface passes
exactly through a grid node, marching cubes emits coincident vertices that
merge into zero-area faces, so those are dropped before validation.
manifold3d then confirms the result (`NoError`), which is also the bar for
the base-opening boolean. Verified watertight at 140, 150, 160, 170, 180 and
200 mm.

MeshFix (`--method meshfix`) also produced a valid solid on this mesh, in the
same time, and keeps the original surface rather than a resampled one. It is
a heuristic repair, so it stays the alternative; voxel is the default because
its guarantee does not depend on the input.

## Result on round1_d

`python tools/mesh_repair.py outputs/scratch/mesh_round1_d.glb --out outputs/stage3_print/round1_d/round1_d_print.stl --height 160 --open-base --views`

| | before (raw at 160 mm) | after (voxel 0.6 mm, 12,000 faces, base cut) |
|---|---|---|
| faces | 271,556 | 11,602 |
| bodies | 1 (+873 debris) | 1 |
| watertight / winding | no / no | yes / yes |
| Euler | 349 | 2 |
| manifold3d | NotManifold | NoError |
| volume | n/a (open) | 404.9 cm³ |
| bear scale | 160.0 mm | 168.0 mm |
| printed height | 160.0 mm | 160.0 mm |
| footprint (printed piece) | 135.9 × 62.7 mm | 142.8 × 66.3 mm |
| needs support | 8.72 % | 6.29 %, worst band z 0–27 mm |
| base openings | – | 2 (one per foot, ≈ 26 × 31 mm) |

Runs in about 8 s. The support that remains is the crotch, the underarms and
the underside of the muzzle; the sheet tints those faces red. The 5 % gate is
not met yet; that is a pose question, not a repair question.

## Defaults and what they cost

- **Pitch 0.6 mm** at print scale (about one nozzle width; `--pitch`). Grid
  is ~230 × 105 × 270 voxels at 160 mm; 0.4 mm is 3× slower and needs the
  closing radius widened, which the tool does on its own when the flood fill
  leaks. Because a voxel the surface passes through counts as solid, the
  remeshed skin grows by about half a pitch; the tool rescales to `--height`
  afterwards, so the residual is only that thin features are ~0.6 mm fatter
  relative to the body.
- **Decimation 12,000 faces** (`--faces`). At 6,000 the open jaw collapses to
  a slit; 12,000 keeps it readable, 20,000 keeps the teeth. See
  `outputs/stage3_print/round1_d/round1_d_faces_ladder.png`. Decimation is
  validated; if it breaks the solid it retries gentler and finally keeps the
  dense mesh.
- **Open base 8 mm** (`--open-base`, `--base`). `--height` is the printed
  height, what comes off the plate. The bear is scaled to `--height + --base`
  (168 mm), the bottom 8 mm are removed, and the piece is exactly 160 mm tall.
  The table shows both: `bear scale` and `printed height`, and the footprint
  is the printed piece's. Without `--open-base` the two are the same number.

## Quality sweep, 2026-09-10: what to change for a smoother, more faithful bear

Full numbers, tables and sheets: `outputs/stage3_print/quality/report.md`
(bears c and o from round2z, plus round-3 b and d for the leg fill). The
sweep tool is `tools/mesh_sweep.py`; every part below is reproducible from
it. Recommended stage-3 line:

```
python tools/mesh_repair.py <bear>.glb --out <bear>_print.stl --height 160 --open-base \
    --pitch 0.4 --iso 0.7 --faces 25000 --smooth --fill-legs hull --views
```

- **Fidelity is set by the pitch and by nothing else.** Mean distance from the
  repaired surface back to the original shell: 0.27 / 0.18 / 0.13 mm at
  0.6 / 0.4 / 0.3 mm pitch. Faces (12k to 50k) and Taubin move it by less than
  0.01 mm. Those means are pitch/2: they are the half-pitch skin growth, a
  bias, not lost detail. **`--iso 0.7`** pulls the isosurface half a voxel back
  in and removes it: 0.05 to 0.06 mm mean at 0.4 mm pitch (0.09 to 0.11 at
  0.6), thin features 0.3 to 0.4 mm slimmer, volume 1.2 % smaller, nothing
  else changes. 0.4 mm at iso 0.7 is more faithful than 0.3 mm at 0.5 in
  two-thirds the time. 0.3 mm (16 to 18 M solid voxels, 35 s) buys 0.05 mm
  over 0.4 and is not worth it.
- **`--smooth` (Taubin x10 on the dense remesh)** takes the voxel terracing
  out of the skin; it is visible at 0.6 mm and still at 0.4 mm
  (`quality/c/c_head_closeups.png`). Fidelity is unchanged, support % drops
  0.05 to 0.1 points.
- **25,000 faces.** 12,000 facets the muzzle and ears at 160 mm
  (`quality/c/c_head_faces_ladder.png`); 50,000 is barely smoother for twice
  the file (2.3 MB vs 1.15 MB). The low-poly look of the old 12k default was a
  choice, not a limit.
- **Support % does not respond to any of the above** (c 5.1 to 5.4, o 6.2 to
  6.4 across all 36 cells) and **tilting does not help**: the best lean within
  +/-15 deg saves 0.13 points on c and 0.46 on o, at the cost of a taller,
  wider print. The overhang is the crotch and the underarms, a pose problem.
- **`--fill-legs hull` fixes the crotch.** It unions a convex block of the
  leg band (from where the horizontal slices split into two legs up to the
  crotch + 4 mm) with the bear: c 5.31 -> 3.32 %, o 6.33 -> 4.10 %, and both
  round-3 bears on their rock slabs still gain (b 2.71 -> 1.48, d 4.46 ->
  3.13); all four pass the 5 % gate. `between` clips the block to the feet's
  footprint and leaves a little overhang where the rump bulges behind the
  feet (c 3.94, o 4.59); on the slab bears the two are equal. What remains
  after the fill is the underarms, the raised paws and the underside of the
  muzzle.
- **Nothing is thin at 160 mm.** No surface is under 2.5 mm, 0.0 to 0.1 % is
  under 4 mm (the wedge rim of the base cut, which the first layers fill).
  Ears are 6 to 7 mm, the muzzle lip 5.3 mm (c), the raised paw tips 4.3 mm
  (o). The ears reach 2.5 mm at a 63 mm (c) / 59 mm (o) printed height; at
  iso 0.7 add about 4 mm to that.

Things that bit while building the fill: qhull's convex hull of the 100k
vertices below the crotch came back non-watertight and manifold3d refused
the union, so hulls and booleans are manifold3d's (`Manifold.hull_points`);
the hull of "everything below the crotch" turns a rock slab into a 38 mm cone,
so the block is the hull of the leg band only, sunk 4 mm into whatever is
beneath; the union output carries a few zero-volume six-triangle bubbles and
sliver faces, so the largest decomposed piece is kept and trimesh's vertex
merge is skipped on it. Quadric decimation always breaks the solid after a
boolean; `decimate` falls back to manifold3d's simplify (bisected on a face
target), which is where the extra 10 s of `--fill-legs` goes.

## The Y-up gotcha

glTF/GLB is Y-up. STL, slicers and every number in these tools are Z-up.
Measure a GLB as Z-up and the bear lies on its back: 346 × 408 mm footprint,
overhang census meaningless. `check_mesh.guess_up` picks Y for `.glb/.gltf`
and Z for everything else; `--up y|z` overrides. Every tool here goes through
it, and everything written out (STL, PNG) is Z-up with the feet on z = 0 and
the front facing −Y.

## CLI

```
python check_mesh.py <mesh> [--height 160] [--up auto|y|z] [--limit 45] [--export out.stl]
    watertight, winding, footprint, height, volume, overhang census by z-band.
    exit 0 only if watertight and < 5 % needs support.

python tools/mesh_repair.py <mesh> --out out.stl [--height 160] [--open-base] [--base 8]
        [--method voxel|meshfix|fill|none] [--pitch 0.6] [--iso 0.5] [--smooth [10]]
        [--fill-legs hull|between] [--faces 12000] [--views [sheet.png]]
    orient, scale, keep largest shell, remesh (marching cubes at --iso; 0.7
    undoes the half-pitch skin growth), validate (watertight / winding / Euler /
    manifold3d), Taubin-smooth (--smooth), fill the gap between the hind legs
    (--fill-legs), decimate, fix winding, optional base cut, before/after table,
    STL. A bare --views writes <out>_views.png beside the STL. Same exit code
    as check_mesh.

python tools/mesh_sweep.py grid <mesh> --out <dir> [--pitch 0.6 0.4 0.3] [--faces 12000 25000 50000]
        [--smooth 0 10] [--iso 0.5]
python tools/mesh_sweep.py tilt <mesh> --out <dir> [--pitch 0.4] [--faces 25000] [--smooth 10] [--max-deg 15] [--step 5]
python tools/mesh_sweep.py legs <mesh> --out <dir> [--pitch 0.4] [--faces 25000] [--smooth 10]
python tools/mesh_sweep.py thickness <printed.stl> --out <dir> [--samples 20000]
    quality sweeps, CPU only: grid = one STL + sheet + row per pitch x faces x
    smoothing (solid?, tris, support %, fidelity to the original shell, size,
    wall time; resumes from <dir>/grid.json); tilt = lean about X and Y and
    re-cut the base; legs = none / hull / between; thickness = ray-cast local
    thickness census with the thin faces coloured. Each writes <dir>/<name>.md
    and .json.

python tools/mesh_views.py <mesh> [--height 160] [--out sheet.png] [--limit 45] [--render-faces 60000]
    six orthographic views (front, left, back, right, top, three-quarter) on one
    sheet, red = needs support, footer with the check_mesh numbers.

python tools/mesh_batch.py <dir> [--height 160] [--ext glb stl]
    mesh_views for every .glb and .stl in a directory plus <dir>/mesh_report.md
    ranked watertight-first, then least support. Files that fail to load get a
    "failed" row; a.glb and a.stl side by side get a_glb_views.png / a_stl_views.png.
```

Views use Blender's naming: front looks at −Y, left from −X, right from +X,
top with the front at the bottom of the panel.
