# outputs/stage2_mesh/round2z_o384 — octree 384 vs 256

The eight three-quarter-view candidates (c d g i / k o q s) reconstructed again with
`vaedecodehunyuan3d_octree_resolution: 384` (blueprint `stage2_round2z_o384.yaml`; same rembg
cutout, 30 steps, seed 1). Numbers from `check_mesh.py --up auto --height 160`; the 256 column is
the same id in `../round2z/`. None of the sixteen meshes is watertight (see `tools/mesh_repair.py`).
The two views sheets of every id were compared side by side at print scale.

**Verdict: octree 384 changes nothing you can see at 160 mm.** 2.1–2.3× the triangles, footprints
equal to 0.1 mm, support within 0.1 percentage points, red support patches in the same places, no
extra jaw, claw or ear detail on any of the eight. The 256 / 30 steps / threshold 0.6 default stands.

| id | tris 256 | tris 384 | support 256 | support 384 | footprint 256 | footprint 384 | views | visual verdict (384 vs 256) |
|---|---:|---:|---:|---:|---:|---:|---|---|
| c | 254,140 | 570,960 (2.25×) | 8.23% | 8.27% | 85.9 x 80.0 mm | 85.8 x 79.9 mm | [256](../round2z/c_views.png) · [384](c_views.png) | nothing new: raised paw, open jaw and ears identical; 384 is only a marginally smoother torso |
| d | 276,292 | 620,280 (2.25×) | 10.17% | 10.18% | 84.5 x 83.2 mm | 84.4 x 83.1 mm | [256](../round2z/d_views.png) · [384](d_views.png) | nothing new: tongue/mouth and both paws already fully present at 256 |
| g | 232,740 | 521,964 (2.24×) | 8.23% | 8.13% | 77.5 x 71.2 mm | 77.4 x 71.1 mm | [256](../round2z/g_views.png) · [384](g_views.png) | nothing new: the chest seam is a sampler artefact and is in both; ears/muzzle identical |
| i | 236,526 | 529,692 (2.24×) | 8.72% | 8.60% | 76.9 x 78.5 mm | 76.8 x 78.4 mm | [256](../round2z/i_views.png) · [384](i_views.png) | nothing new: same chest seam, same paws, same back |
| k | 290,376 | 652,466 (2.25×) | 10.71% | 10.71% | 81.1 x 91.0 mm | 81.0 x 90.9 mm | [256](../round2z/k_views.png) · [384](k_views.png) | nothing new: belly, paws and open mouth identical; support bands identical |
| o | 273,894 | 615,760 (2.25×) | 9.04% | 9.08% | 77.9 x 89.3 mm | 77.8 x 89.2 mm | [256](../round2z/o_views.png) · [384](o_views.png) | nothing new: the separated toes on both paws are already resolved at 256 |
| q | 235,308 | 528,480 (2.25×) | 9.45% | 9.45% | 67.3 x 79.9 mm | 67.2 x 79.9 mm | [256](../round2z/q_views.png) · [384](q_views.png) | nothing new: q has the most surface wrinkle of the set and 256 already carries all of it |
| s | 240,180 | 539,582 (2.25×) | 9.66% | 9.66% | 75.3 x 82.2 mm | 75.2 x 82.1 mm | [256](../round2z/s_views.png) · [384](s_views.png) | nothing new: identical silhouette, ears and paws |
