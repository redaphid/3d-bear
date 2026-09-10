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
        [--method voxel|meshfix|fill|none] [--pitch 0.6] [--faces 12000] [--views [sheet.png]]
    orient, scale, keep largest shell, remesh, validate (watertight / winding /
    Euler / manifold3d), decimate, fix winding, optional base cut, before/after
    table, STL. A bare --views writes <out>_views.png beside the STL. Same exit
    code as check_mesh.

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
