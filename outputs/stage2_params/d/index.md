# outputs/stage2_params/d — mesh index

Hunyuan3D 2.1 output, scaled to 160 mm tall (GLB is Y-up; oriented with `--up auto`). `watertight: no` means run `tools/mesh_repair.py` before trusting the support number. Refresh with `python tools/mesh_index.py <dir>`.

| file | tris | watertight | height | footprint (x × y) | needs support | look |
|---|---:|:---:|---:|---:|---:|---|
| `o256_s30.glb` | 275,954 | **no** | 160.0 mm | 136.2 x 67.0 mm | 8.97% | [cutout](o256_s30_cutout.png) [views](o256_s30_views.png) |
| `o384_s30.glb` | 620,052 | **no** | 160.0 mm | 136.1 x 66.9 mm | 8.95% | [cutout](o384_s30_cutout.png) [views](o384_s30_views.png) |
| `o384_s30_seed2.glb` | 646,014 | **no** | 160.0 mm | 138.1 x 71.7 mm | 9.31% | [cutout](o384_s30_seed2_cutout.png) [views](o384_s30_seed2_views.png) |
| `o384_s30_seed3.glb` | 617,922 | **no** | 160.0 mm | 135.1 x 73.5 mm | 8.63% | [cutout](o384_s30_seed3_cutout.png) [views](o384_s30_seed3_views.png) |
| `o384_s30_t05.glb` | 625,944 | **no** | 160.0 mm | 136.1 x 67.1 mm | 8.96% | [cutout](o384_s30_t05_cutout.png) [views](o384_s30_t05_views.png) |
| `o384_s30_t07.glb` | 615,386 | **no** | 160.0 mm | 136.0 x 66.8 mm | 8.94% | [cutout](o384_s30_t07_cutout.png) [views](o384_s30_t07_views.png) |
| `o512_s30.glb` | 1,103,130 | **no** | 160.0 mm | 136.1 x 67.0 mm | 8.94% | [cutout](o512_s30_cutout.png) [views](o512_s30_views.png) |
| `o384_s50.glb` | 618,812 | **no** | 160.0 mm | 135.6 x 66.8 mm | 8.96% | [cutout](o384_s50_cutout.png) [views](o384_s50_views.png) |

## Octree resolution on d: 256 vs 384 vs 512

| octree | tris | footprint | needs support | views |
|---:|---:|---:|---:|---|
| 256 | 275,954 | 136.2 x 67.0 mm | 8.97% | [o256_s30](o256_s30_views.png) |
| 384 | 620,052 | 136.1 x 66.9 mm | 8.95% | [o384_s30](o384_s30_views.png) |
| 512 | 1,103,130 | 136.1 x 67.0 mm | 8.94% | [o512_s30](o512_s30_views.png) |

Same bear three times: 4.0× the triangles from 256 to 512, footprint and support equal to the
measurement noise (0.1 mm, 0.03 points), and the views sheets show the same silhouette, ears, jaw
and paws; 512 only smooths the surface a little more, and nothing of that survives the 0.6 mm
voxel repair anyway. The 256/30/0.6 default stands. The octree-384 pass on eight round-2z
candidates (`../../stage2_mesh/round2z_o384/index.md`) reached the same verdict.
