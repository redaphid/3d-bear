# Stage-3 mesh quality sweep: pitch × faces × smoothing, tilt, thin features, leg fill

Bears **c** and **o** from `outputs/stage2_mesh/round2z/`, plus the round-3 candidates **b** and **d**
(`outputs/stage2_mesh/round3z/`, byte-identical to `D:/sync/Comfy/3d-bear/stage2_mesh/round3z/b_00001_.glb`
and `d_00001_.glb`) for the leg fill. Everything is at 160 mm printed height with the 8 mm open base,
CPU only, produced by `tools/mesh_sweep.py` (grid / tilt / thickness / legs) and `tools/mesh_repair.py`.
Per-bear tables and JSON live beside this file in `c/`, `o/`, `b/`, `d/`; every cell has a six-view sheet.

## Recommendation

Adopt **pitch 0.4 mm, isolevel 0.7, 25,000 faces, Taubin ×10, `--fill-legs hull`**, i.e.

```
python tools/mesh_repair.py <bear>.glb --out <bear>_print.stl --height 160 --open-base \
    --pitch 0.4 --iso 0.7 --faces 25000 --smooth --fill-legs hull --views
```

Against today's default (0.6 mm, 12,000 faces, no smoothing, no fill) this takes the mean distance from
the printed surface to the original Hunyuan shell from 0.27 mm to 0.05–0.06 mm (95th percentile 0.46 →
0.13–0.15 mm), removes the voxel terracing and the 12k faceting from the muzzle and ears, and cuts the
support census from 5.31 % to 3.28 % on c and from 6.33 % to 4.00 % on o, so both pass the 5 % gate for
the first time; the round-3 slab bears go from 2.71 % to 1.52 % (b) and 4.46 % to 3.17 % (d). The cost
is 36–46 s per bear instead of 8 s and a 1.2 MB STL instead of 0.57 MB. The pitch is what buys fidelity
(faces and smoothing change it by under 0.01 mm), and `--iso 0.7` matters more than going to 0.3 mm
because the grid's residual error is the remesh's half-pitch skin growth, a bias, not lost detail; 0.4 mm
at level 0.7 is more faithful than 0.3 mm at 0.5 in two-thirds the time. Tilting the bear is not worth
doing (best lean saves 0.13 points on c, 0.46 on o). Nothing on either bear is under 4 mm thick at
160 mm, so no minimum-feature concern until about 65 mm printed height.

### The recommended STLs

| bear | raw support % | recommended support % | tris | volume cm³ | footprint mm | KB | wall s | files |
|---|---:|---:|---:|---:|---|---:|---:|---|
| c | 8.23 | **3.28** | 23,730 | 430.4 | 90.3 x 83.8 | 1,158 | 36 | `c/c_recommended.stl`, `c/c_recommended_views.png` |
| o | 9.04 | **4.00** | 24,120 | 500.4 | 81.6 x 93.5 | 1,177 | 42 | `o/o_recommended.stl`, `o/o_recommended_views.png` |
| b | 13.32 | **1.52** | 22,240 | 363.5 | 85.1 x 69.9 | 1,086 | 39 | `b/b_recommended.stl`, `b/b_recommended_views.png` |
| d | 16.46 | **3.17** | 23,376 | 465.3 | 95.7 x 84.6 | 1,141 | 46 | `d/d_recommended.stl`, `d/d_recommended_views.png` |

`hull` was chosen over `between` because on the plate bears the rump bulges behind the feet and the
clipped block leaves that overhang (c 3.94 vs 3.32 %, o 4.59 vs 4.10 %); on the slab bears the two are
within 0.1 points of each other. What support remains after the fill is the underarms and raised paws
(z 53–107 mm) and the underside of the muzzle; those are pose, not repair.

## Part A: surface-quality grid

Grid over pitch {0.6, 0.4, 0.3} mm × decimation target {12,000, 25,000, 50,000} × smoothing {none,
Taubin ×10}, 18 cells per bear, each cell a printed piece (base cut) with its six-view sheet at
`<bear>/<cell>_views.png`. *solid* = watertight, winding-consistent and manifold3d `NoError` on the
printed piece. Fidelity is measured on the closed bear before the base cut, at bear scale (168 mm), over
20,000 area-uniform samples with `trimesh.proximity.closest_point`: *back* is repaired → original largest
shell (mean and 95th percentile, mm), *fwd p95* is original → repaired (what a filled mouth or a lost claw
would show up in). Wall time is remesh + finish for that cell, single process. The remesh is done once
per pitch and shared by its six cells.

**0.3 mm was run rather than dropped.** It is 15.8 M (c) / 18.3 M (o) solid voxels in a 47–48 M-cell
grid, so it is well over the 2 M-voxel line, but it remeshed in 23–29 s (35 s per cell end to end) with no
memory trouble on this box. It is in the tables so the decision is on the numbers: it buys 0.05 mm of mean
error over 0.4 mm, which `--iso 0.7` buys three times over at 0.4 mm.

The extra `_iso0.7` rows (25,000 faces, Taubin) were added after the isolevel finding below; their wall
times are inflated because they ran alongside seven other jobs.

### c

Printed height 160 mm, base cut 8 mm. Fidelity is mm at print scale over 20,000 samples; 'back' is repaired->original, 'fwd' is original->repaired (large fwd p95 = lost detail).

| pitch | grid | solid voxels | dense tris | remesh s |
|---:|---|---:|---:|---:|
| 0.6 | 151x141x281 | 2,010,026 | 315,388 | 6 |
| 0.6@0.7 | 151x141x281 | 2,010,026 | 308,232 | 16 |
| 0.4 | 227x211x421 | 6,701,291 | 706,724 | 17 |
| 0.4@0.7 | 227x211x421 | 6,701,291 | 696,248 | 30 |
| 0.3 | 301x281x561 | 15,785,819 | 1,253,624 | 29 |

| cell | solid | tris | support % | back mean | back p95 | fwd p95 | KB | wall s |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| `c_p0.6_f12000_none` | yes | 11,632 | 5.24 | 0.275 | 0.458 | 0.466 | 568 | 12 |
| `c_p0.6_f12000_taubin` | yes | 11,398 | 5.14 | 0.265 | 0.476 | 0.480 | 556 | 11 |
| `c_p0.6_f25000_none` | yes | 24,058 | 5.15 | 0.276 | 0.465 | 0.466 | 1,174 | 11 |
| `c_p0.6_f25000_taubin` | yes | 23,490 | 5.11 | 0.275 | 0.487 | 0.494 | 1,147 | 12 |
| `c_p0.6_f50000_none` | yes | 47,836 | 5.09 | 0.274 | 0.471 | 0.474 | 2,335 | 12 |
| `c_p0.6_f50000_taubin` | yes | 46,808 | 5.11 | 0.272 | 0.482 | 0.493 | 2,285 | 12 |
| `c_p0.6_f25000_taubin_iso0.7` | yes | 23,506 | 5.15 | 0.108 | 0.261 | 0.266 | 1,147 | 28 |
| `c_p0.4_f12000_none` | yes | 11,664 | 5.36 | 0.177 | 0.311 | 0.310 | 569 | 23 |
| `c_p0.4_f12000_taubin` | yes | 11,444 | 5.29 | 0.182 | 0.313 | 0.315 | 558 | 23 |
| `c_p0.4_f25000_none` | yes | 24,092 | 5.36 | 0.185 | 0.314 | 0.313 | 1,176 | 22 |
| `c_p0.4_f25000_taubin` | yes | 23,632 | 5.31 | 0.178 | 0.315 | 0.317 | 1,153 | 23 |
| `c_p0.4_f50000_none` | yes | 47,968 | 5.36 | 0.187 | 0.318 | 0.317 | 2,342 | 22 |
| `c_p0.4_f50000_taubin` | yes | 46,850 | 5.30 | 0.180 | 0.319 | 0.322 | 2,287 | 27 |
| `c_p0.4_f25000_taubin_iso0.7` | yes | 23,580 | 5.40 | 0.061 | 0.145 | 0.142 | 1,151 | 45 |
| `c_p0.3_f12000_none` | yes | 11,656 | 5.35 | 0.130 | 0.238 | 0.235 | 569 | 36 |
| `c_p0.3_f12000_taubin` | yes | 11,486 | 5.40 | 0.132 | 0.227 | 0.228 | 560 | 37 |
| `c_p0.3_f25000_none` | yes | 24,114 | 5.40 | 0.138 | 0.240 | 0.240 | 1,177 | 34 |
| `c_p0.3_f25000_taubin` | yes | 23,688 | 5.33 | 0.134 | 0.243 | 0.242 | 1,156 | 37 |
| `c_p0.3_f50000_none` | yes | 48,048 | 5.42 | 0.140 | 0.234 | 0.232 | 2,346 | 35 |
| `c_p0.3_f50000_taubin` | yes | 46,910 | 5.35 | 0.135 | 0.241 | 0.240 | 2,290 | 37 |

### o

Printed height 160 mm, base cut 8 mm. Fidelity is mm at print scale over 20,000 samples; 'back' is repaired->original, 'fwd' is original->repaired (large fwd p95 = lost detail).

| pitch | grid | solid voxels | dense tris | remesh s |
|---:|---|---:|---:|---:|
| 0.6 | 137x157x281 | 2,325,840 | 339,924 | 7 |
| 0.6@0.7 | 137x157x281 | 2,325,840 | 332,096 | 16 |
| 0.4 | 205x235x421 | 7,759,570 | 761,516 | 18 |
| 0.4@0.7 | 205x235x421 | 7,759,570 | 749,974 | 33 |
| 0.3 | 273x313x561 | 18,286,718 | 1,350,856 | 23 |

| cell | solid | tris | support % | back mean | back p95 | fwd p95 | KB | wall s |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| `o_p0.6_f12000_none` | yes | 11,640 | 6.31 | 0.268 | 0.455 | 0.454 | 568 | 14 |
| `o_p0.6_f12000_taubin` | yes | 11,430 | 6.20 | 0.253 | 0.479 | 0.480 | 558 | 12 |
| `o_p0.6_f25000_none` | yes | 24,040 | 6.27 | 0.267 | 0.454 | 0.453 | 1,173 | 12 |
| `o_p0.6_f25000_taubin` | yes | 23,570 | 6.18 | 0.254 | 0.479 | 0.484 | 1,150 | 13 |
| `o_p0.6_f50000_none` | yes | 47,946 | 6.22 | 0.269 | 0.452 | 0.456 | 2,341 | 12 |
| `o_p0.6_f50000_taubin` | yes | 46,968 | 6.16 | 0.256 | 0.472 | 0.482 | 2,293 | 13 |
| `o_p0.6_f25000_taubin_iso0.7` | yes | 23,576 | 6.22 | 0.090 | 0.229 | 0.241 | 1,151 | 29 |
| `o_p0.4_f12000_none` | yes | 11,696 | 6.36 | 0.177 | 0.293 | 0.291 | 571 | 25 |
| `o_p0.4_f12000_taubin` | yes | 11,456 | 6.24 | 0.165 | 0.312 | 0.309 | 559 | 25 |
| `o_p0.4_f25000_none` | yes | 24,238 | 6.36 | 0.180 | 0.303 | 0.301 | 1,183 | 23 |
| `o_p0.4_f25000_taubin` | yes | 23,690 | 6.33 | 0.171 | 0.301 | 0.303 | 1,156 | 25 |
| `o_p0.4_f50000_none` | yes | 48,324 | 6.36 | 0.181 | 0.302 | 0.300 | 2,359 | 24 |
| `o_p0.4_f50000_taubin` | yes | 47,020 | 6.29 | 0.174 | 0.302 | 0.302 | 2,295 | 30 |
| `o_p0.4_f25000_taubin_iso0.7` | yes | 23,656 | 6.31 | 0.049 | 0.125 | 0.125 | 1,155 | 49 |
| `o_p0.3_f12000_none` | yes | 11,684 | 6.26 | 0.128 | 0.220 | 0.217 | 570 | 33 |
| `o_p0.3_f12000_taubin` | yes | 11,528 | 6.31 | 0.128 | 0.235 | 0.235 | 562 | 32 |
| `o_p0.3_f25000_none` | yes | 24,252 | 6.30 | 0.133 | 0.228 | 0.224 | 1,184 | 29 |
| `o_p0.3_f25000_taubin` | yes | 23,742 | 6.31 | 0.129 | 0.227 | 0.223 | 1,159 | 35 |
| `o_p0.3_f50000_none` | yes | 48,350 | 6.36 | 0.135 | 0.226 | 0.223 | 2,360 | 30 |
| `o_p0.3_f50000_taubin` | yes | 47,134 | 6.31 | 0.129 | 0.224 | 0.223 | 2,301 | 34 |

### What the grid says

- **All 36 (+4) cells are solids.** Decimation never had to fall back; the base cut always left one
  opening.
- **Fidelity depends on the pitch and on nothing else.** Mean back-distance 0.27 / 0.18 / 0.13 mm at
  0.6 / 0.4 / 0.3 mm on both bears. Faces from 12k to 50k move it by < 0.01 mm; Taubin lowers the mean
  by ~0.01 and raises p95 by ~0.02 at 0.6 mm (it rounds the terrace edges both ways). Those means are
  pitch/2, which is exactly the skin growth `voxel_remesh` documents: a voxel the surface passes through
  counts as solid, so the 0.5 isosurface sits half a pitch outside the true surface everywhere. The
  number is a bias, not detail loss, and it is the same size on the ears as on the belly.
- **The bias comes out with the isolevel.** The field is a one-voxel Gaussian of the occupancy, so a
  level above 0.5 moves the surface inward by a fraction of a voxel. Sweep on c and o at 0.4 mm and c at
  0.6 mm (25,000 faces, Taubin):

| bear, pitch | level | back mean | back p95 | back max | fwd p95 | fwd max | volume cm³ | support % | thickness p1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| c, 0.4 mm | 0.50 | 0.178 | 0.315 | 0.79 | 0.317 | 1.07 | 425.3 | 5.31 | 6.83 |
| c, 0.4 mm | 0.60 | 0.117 | 0.208 | 0.80 | 0.208 | 0.85 | 422.9 | 5.37 | 6.61 |
| c, 0.4 mm | 0.69 | 0.055 | 0.123 | 0.72 | 0.118 | 0.74 | 420.3 | 5.34 | 6.43 |
| c, 0.4 mm | 0.75 | 0.046 | 0.122 | 0.59 | 0.119 | 0.73 | 418.6 | 5.40 | 6.26 |
| c, 0.4 mm | 0.80 | 0.061 | 0.160 | 0.64 | 0.161 | 0.67 | 417.2 | 5.43 | 6.13 |
| o, 0.4 mm | 0.50 | 0.171 | 0.301 | 0.87 | 0.303 | 1.00 | 492.5 | 6.33 | 7.60 |
| o, 0.4 mm | 0.60 | 0.110 | 0.195 | 0.81 | 0.199 | 0.88 | 489.9 | 6.30 | 7.54 |
| o, 0.4 mm | 0.69 | 0.054 | 0.113 | 0.64 | 0.116 | 0.78 | 487.3 | 6.32 | 7.21 |
| o, 0.4 mm | 0.75 | 0.042 | 0.120 | 0.65 | 0.119 | 0.71 | 485.6 | 6.31 | 6.92 |
| o, 0.4 mm | 0.80 | 0.053 | 0.161 | 0.63 | 0.163 | 0.61 | 484.0 | 6.36 | 6.76 |
| c, 0.6 mm | 0.50 | 0.275 | 0.487 | 1.31 | 0.494 | 1.78 | 429.0 | 5.11 | 7.25 |
| c, 0.6 mm | 0.60 | 0.172 | 0.345 | 1.29 | 0.352 | 1.63 | 424.9 | 5.16 | 6.98 |
| c, 0.6 mm | 0.69 | 0.111 | 0.266 | 1.10 | 0.264 | 1.55 | 421.0 | 5.15 | 6.55 |
| c, 0.6 mm | 0.75 | 0.086 | 0.227 | 1.08 | 0.237 | 1.40 | 418.9 | 5.18 | 6.38 |
| c, 0.6 mm | 0.80 | 0.097 | 0.276 | 0.98 | 0.282 | 1.29 | 416.7 | 5.18 | 6.20 |

  0.69–0.75 is the optimum at both pitches on both bears (mean error ÷ 3.3 at 0.4 mm, ÷ 2.5 at 0.6 mm);
  by 0.80 it has gone past the surface and the error climbs again. Volume drops 1.2 % (the skin was
  inflating it) and the thinnest 1 % of the surface gets 0.3–0.4 mm slimmer (the same skin, on both sides
  of a feature); support % does not move. `--iso 0.7` is now a flag on `mesh_repair.py`, default still
  0.5. The `_iso0.7` grid rows above show it in the standard measurement: c 0.061 / 0.145 mm and o
  0.049 / 0.125 mm mean / p95 at 0.4 mm.
- **Support % is flat across the grid** (c 5.09–5.42, o 6.16–6.36). No repair setting touches the
  overhang; that is Part D's job.
- **Smoothing is a visual, not a metric, win.** `c/c_head_closeups.png` (25,000 faces, pitch × smoothing,
  front and three-quarter) shows the voxel terracing across the muzzle and forehead at 0.6 mm, still
  faintly at 0.4 mm, gone with Taubin at either; 0.3 mm without smoothing is about as clean as 0.4 mm
  with it. Taubin ×10 on the dense mesh costs 1.5 s and validates.
- **12,000 faces facets the head.** `c/c_head_faces_ladder.png` (0.4 mm, Taubin, 12k / 25k / 50k): at
  12k the muzzle, lips and ear rims are visibly polygonal at 160 mm; 25k reads as smooth; 50k is a
  little smoother again for twice the file (2.3 MB vs 1.15 MB). The fidelity metric cannot see any of
  this because the facets are within 0.1 mm of the surface; the eye can.
- **Cost.** Wall time per cell 11–14 s at 0.6 mm, 22–30 s at 0.4 mm, 29–37 s at 0.3 mm; STL size is
  set by the face count alone: 0.57 / 1.15 / 2.3 MB at 12k / 25k / 50k.

## Part B: tilt

The closed bear at pitch 0.4, 25,000 faces, Taubin ×10 (isolevel 0.5), rotated about X (+ leans
forward) and about Y (+ leans to the viewer's right) from −15° to +15° in 5° steps, base re-cut 8 mm at
each orientation, support % of the printed piece. Sheets of the best orientation: `c/c_tilt_best_views.png`,
`o/o_tilt_best_views.png`; the STLs are `<bear>_tilt_rx-5_ry+5.stl`.

### c

Rotation about X: + leans forward (face down), - leans back. Rotation about Y: + leans to the viewer's right in the front view. Base re-cut 8 mm at each orientation; support % of the printed piece.

| rx \ ry | -15° | -10° | -5° | +0° | +5° | +10° | +15° |
|---:|---:|---:|---:|---:|---:|---:|---:|
| -15° | 7.10 | 7.02 | 6.27 | 5.42 | 5.95 | 6.53 | 6.46 |
| -10° | 7.08 | 6.98 | 5.98 | 5.39 | 5.70 | 6.43 | 6.27 |
| -5° | 7.15 | 7.02 | 5.44 | 5.41 | **5.18** | 6.57 | 6.38 |
| +0° | 7.41 | 6.96 | 5.23 | 5.31 | 5.20 | 6.63 | 6.49 |
| +5° | 7.90 | 7.54 | 5.59 | 5.53 | 5.45 | 7.03 | 7.04 |
| +10° | 8.53 | 8.36 | 6.89 | 6.08 | 6.47 | 7.68 | 7.83 |
| +15° | 9.36 | 9.04 | 8.03 | 6.90 | 7.67 | 8.65 | 9.01 |

Upright: 5.31 %. Best: rx -5°, ry +5° at 5.18 % (0.13 points saved), printed height 164.4 mm, footprint 88 x 75 mm.

Best within ±10°: rx -5°, ry +5° at 5.18 %.

### o

Rotation about X: + leans forward (face down), - leans back. Rotation about Y: + leans to the viewer's right in the front view. Base re-cut 8 mm at each orientation; support % of the printed piece.

| rx \ ry | -15° | -10° | -5° | +0° | +5° | +10° | +15° |
|---:|---:|---:|---:|---:|---:|---:|---:|
| -15° | 7.65 | 7.45 | 6.70 | 5.92 | 6.84 | 7.67 | 7.87 |
| -10° | 7.52 | 7.35 | 6.34 | 5.86 | 6.51 | 7.37 | 7.57 |
| -5° | 7.68 | 7.48 | 5.92 | 5.87 | **5.86** | 7.48 | 7.67 |
| +0° | 7.91 | 7.71 | 6.19 | 6.33 | 6.25 | 7.70 | 7.90 |
| +5° | 8.45 | 8.38 | 6.87 | 6.84 | 6.82 | 8.32 | 8.47 |
| +10° | 9.02 | 8.84 | 7.95 | 7.36 | 7.95 | 8.85 | 8.94 |
| +15° | 9.89 | 9.59 | 8.87 | 8.01 | 8.80 | 9.41 | 9.64 |

Upright: 6.33 %. Best: rx -5°, ry +5° at 5.86 % (0.46 points saved), printed height 162.2 mm, footprint 87 x 89 mm.

Best within ±10°: rx -5°, ry +5° at 5.86 %.

**Tilt is not the lever.** The best lean (−5° back, +5° sideways) saves 0.13 points on c and 0.46 on o,
and every lean past 5° costs support because the belly, muzzle and paw undersides tip over faster than
the crotch closes. The tilted piece is also taller (162–164 mm for the same bear), wider, and its base
opening moves off-centre. Upright with the leg fill (Part D) saves 2.0–2.2 points; that is the answer.

## Part C: thin features

Ray-cast local thickness on the printed piece (`c_p0.4_f25000_taubin.stl`, `o_p0.4_f25000_taubin.stl`)
at 20,000 area-uniform samples (`trimesh.proximity.thickness`, method `ray`). *Under 2.5 mm* is two walls
of a 0.6 mm nozzle, *under 4 mm* is comfortable. The wedge rim within 2 mm of the base cut is left out of
the census (the cut leaves a sliver where the plate meets the curved feet; the first layers fill it).
Ears = thin material in the top tenth of the model near the head's axis. The sheets with the thin faces
coloured (red < 2.5 mm, orange 2.5–4 mm) are `c/c_p0.4_f25000_taubin_thickness_views.png` and
`o/o_p0.4_f25000_taubin_thickness_views.png`; they are plain grey apart from the rim wedge, which is the
finding.

### c

| under 2.5 mm | under 4 mm | ears p10 | ears median | height for 2.5 mm ears |
|---:|---:|---:|---:|---:|
| 0.0 % of surface | 0.0 % | 6.3 mm | 6.9 mm | 63 mm |

The wedge rim within 2 mm of the base cut is left out (0.6 % of the surface is under 2.5 mm there; the first layers fill it).

Where (share of total surface, by height band): under 2.5 mm

- z 0-27 mm: 0.0 % (median 2.3 mm)

under 4 mm

- z 0-27 mm: 0.0 % (median 3.4 mm)

Thinnest spots (the thinnest 2 % of samples, clustered within 6 mm; x + is the viewer's right in the front view, y - is the front):

| where | x | y | min mm | median mm | samples |
|---|---:|---:|---:|---:|---:|
| z 2 mm, viewer's left, middle | -27 | -6 | 2.3 | 3.9 | 15 |
| z 128 mm, centre, front | -1 | -30 | 5.3 | 6.6 | 93 |
| z 154 mm, viewer's left, middle | -19 | 4 | 5.8 | 6.9 | 151 |
| z 153 mm, viewer's right, middle | 22 | 5 | 5.9 | 6.8 | 123 |

Sheet: `c_p0.4_f25000_taubin_thickness_views.png`

### o

| under 2.5 mm | under 4 mm | ears p10 | ears median | height for 2.5 mm ears |
|---:|---:|---:|---:|---:|
| 0.0 % of surface | 0.1 % | 6.7 mm | 7.1 mm | 59 mm |

The wedge rim within 2 mm of the base cut is left out (0.8 % of the surface is under 2.5 mm there; the first layers fill it).

Where (share of total surface, by height band): under 2.5 mm


under 4 mm

- z 0-27 mm: 0.1 % (median 3.3 mm)

Thinnest spots (the thinnest 2 % of samples, clustered within 6 mm; x + is the viewer's right in the front view, y - is the front):

| where | x | y | min mm | median mm | samples |
|---|---:|---:|---:|---:|---:|
| z 2 mm, viewer's left, middle | -32 | -6 | 2.5 | 4.3 | 18 |
| z 102 mm, viewer's right, front | 18 | -39 | 4.3 | 11.2 | 84 |
| z 154 mm, viewer's right, middle | 21 | -4 | 6.3 | 7.3 | 136 |
| z 151 mm, viewer's left, middle | -23 | 1 | 6.6 | 7.1 | 113 |
| z 97 mm, viewer's left, front | -16 | -41 | 6.9 | 10.5 | 24 |

Sheet: `o_p0.4_f25000_taubin_thickness_views.png`

**Nothing is thin at 160 mm.** No surface is under 2.5 mm and 0.0–0.1 % is under 4 mm (all of it the rim
wedge). The thinnest real features, thinnest first: on c the muzzle lip / open jaw (5.3 mm, z 128 mm,
centre front) and the two ears (5.8 and 5.9 mm, z 153–154 mm); on o the raised paw tips (4.3 mm minimum
at z 102 mm, front right) and the ears (6.3 and 6.6 mm). Neither bear has separate claws or a distinct tail
at this scale; the Hunyuan mesh fuses the claws into the paw and the tail is a rounded bump on the
rump (see the back views), both well over 4 mm. The ears (10th percentile 6.3 mm on c, 6.7 mm on o) reach 2.5 mm at a printed
height of **63 mm (c) / 59 mm (o)**; at `--iso 0.7` features are ~0.4 mm slimmer, which moves that to about
67 / 63 mm. The 100 mm variant of o (`outputs/stage3_print/round2z/o_print_100mm.stl`) has ~4 mm ears.

## Part D: crotch fill (`--fill-legs hull|between`)

Added to `mesh_repair.py` after the voxel remesh and Taubin, before decimation. The crotch is found by
scanning horizontal slices upward in 1 mm steps: the leg band starts where a slice first has two regions
(the plate itself for c and o, the top of the rock slab for b and d) and the crotch is the first slice
above that with one region. The block is manifold3d's convex hull of every vertex in that band up to the
crotch + 4 mm; on a slab bear the footprint outline is copied 4 mm downward so the block is sunk into the
slab and the union has no seam. `between` intersects the block with the vertical extrusion of the feet's
footprint hull (the section 1 mm above the band start) so it cannot bulge in front of or behind the feet.
Union via manifold3d, re-validated; quadric decimation always breaks the solid on a boolean result, so
`decimate` falls back to manifold3d's simplify bisected onto the face target (the extra ~10 s). Setting:
pitch 0.4, 25,000 faces, Taubin ×10, isolevel 0.5 so the *none* rows match the Part A cells. Sheets:
`<bear>/<bear>_legs_{none,hull,between}_views.png`.

### c

`hull` stands the bear in the convex hull of the leg band (from where the slices split into two legs up to the crotch + 4 mm, sunk 4 mm into a slab if there is one); `between` clips that hull to the feet's footprint so only the gap itself is filled. Support % of the printed piece.

| variant | solid | legs from z | crotch z | block to z | sunk | added cm³ | tris | support % | saved | worst band |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| none | yes | - | - | - | - | 0.0 | 23,632 | 5.31 | 0.00 | z 0-27 (859 mm²) |
| hull | yes | 0 | 24 | 28 | 0 | 29.7 | 24,072 | 3.32 | 1.98 | z 80-107 (329 mm²) |
| between | yes | 0 | 24 | 28 | 0 | 23.0 | 24,752 | 3.94 | 1.37 | z 0-27 (394 mm²) |

### o

`hull` stands the bear in the convex hull of the leg band (from where the slices split into two legs up to the crotch + 4 mm, sunk 4 mm into a slab if there is one); `between` clips that hull to the feet's footprint so only the gap itself is filled. Support % of the printed piece.

| variant | solid | legs from z | crotch z | block to z | sunk | added cm³ | tris | support % | saved | worst band |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| none | yes | - | - | - | - | 0.0 | 23,690 | 6.33 | 0.00 | z 0-27 (1478 mm²) |
| hull | yes | 0 | 24 | 28 | 0 | 34.3 | 23,954 | 4.10 | 2.23 | z 53-80 (643 mm²) |
| between | yes | 0 | 24 | 28 | 0 | 27.3 | 24,670 | 4.59 | 1.74 | z 0-27 (810 mm²) |

### b (round 3, on a rock slab)

`hull` stands the bear in the convex hull of the leg band (from where the slices split into two legs up to the crotch + 4 mm, sunk 4 mm into a slab if there is one); `between` clips that hull to the feet's footprint so only the gap itself is filled. Support % of the printed piece.

| variant | solid | legs from z | crotch z | block to z | sunk | added cm³ | tris | support % | saved | worst band |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| none | yes | - | - | - | - | 0.0 | 23,120 | 2.71 | 0.00 | z 0-27 (650 mm²) |
| hull | yes | 13 | 30 | 34 | 4 | 34.0 | 23,064 | 1.48 | 1.22 | z 27-53 (222 mm²) |
| between | yes | 13 | 30 | 34 | 4 | 27.8 | 22,348 | 1.38 | 1.32 | z 27-53 (219 mm²) |

### d (round 3, on a rock slab)

`hull` stands the bear in the convex hull of the leg band (from where the slices split into two legs up to the crotch + 4 mm, sunk 4 mm into a slab if there is one); `between` clips that hull to the feet's footprint so only the gap itself is filled. Support % of the printed piece.

| variant | solid | legs from z | crotch z | block to z | sunk | added cm³ | tris | support % | saved | worst band |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| none | yes | - | - | - | - | 0.0 | 23,578 | 4.46 | 0.00 | z 27-53 (984 mm²) |
| hull | yes | 17 | 34 | 38 | 4 | 51.4 | 23,368 | 3.13 | 1.32 | z 80-107 (560 mm²) |
| between | yes | 17 | 34 | 38 | 4 | 39.4 | 24,202 | 3.08 | 1.38 | z 80-107 (560 mm²) |

**The fill works on all four, slab or not.** c 5.31 → 3.32 %, o 6.33 → 4.10 %, b 2.71 → 1.48 %, d
4.46 → 3.13 % with `hull`; every one passes the 5 % gate. On the slab bears the legs still stand apart
above the slab (band from z 13 mm on b, 17 mm on d), so the crotch was still an overhang and the block
takes it out just the same, seated on the rock; the slab keeps its shape (`d/d_legs_hull_views.png`). The
worst band moves from the crotch (z 0–27 or 27–53) to the underarms (z 53–107). `between` leaves the rump
overhang on the plate bears (its worst band stays at z 0–27) and is a wash on the slab bears; `hull`
adds 30–50 cm³ of plinth, `between` 23–39.

Three things went wrong on the way and are fixed in the tool: qhull's convex hull of the ~100k vertices
below the crotch came back non-watertight (Euler 0) on c and b, and manifold3d refused the union
(o only worked by luck); the hull of "everything below the crotch" turned d's rock slab into a 38 mm
truncated cone (the first d run, now overwritten); and the boolean output carries four six-triangle
zero-volume bubbles plus sliver faces that trimesh's vertex merge turns into non-manifold edges, so the
tool keeps the largest decomposed piece and skips the merge on boolean and simplify output.

## Files

- `report.md` (this), `<bear>/grid.md|json`, `tilt.md|json`, `thickness.md|json`, `legs.md|json`,
  `c/iso_levels_p0.4.json`, `c/iso_levels_p0.6.json`, `o/iso_levels_p0.4.json`.
- Sheets: one `_views.png` per grid cell, tilt best, legs variant, and thickness (`39 MB of PNG in all).
- STLs committed: `<bear>/<bear>_recommended.stl` for c, o, b, d. The grid, tilt and legs STLs are
  regenerable from `mesh_sweep.py` and stay out of git.
