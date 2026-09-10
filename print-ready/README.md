# print-ready — files you can drop straight into the slicer

Every STL here is a validated solid (watertight, consistent winding, Euler 2,
manifold3d clean). Round-3 files use the recipe from `outputs/stage3_print/quality/report.md`:
0.4 mm voxel pitch at iso 0.7 (0.05 mm mean surface error), Taubin-smoothed, 25k faces, and the
gap between the hind legs filled as a block sunk into the plinth (`--fill-legs hull`). Older files
are 0.6 mm / 12k faces. All are scaled so
the **printed piece is the height in the filename**, with the bottom 8 mm cut
away so the base is open for the light and the pole.

| file | pose | footprint | needs support | notes |
|---|---|---|---|---|
| `bear-r3l-bronze-sky-roar-on-rock-160mm.stl` | **round 3, bronze, on a rock**: grizzly anatomy, both arms up roaring at the sky, rock plinth, gap between the legs filled as a carved block | 82 x 63 mm | **0.5 %** | **RECOMMENDED — print this one.** Smoothed 25k-face surface; the only red is two fingertips |
| `bear-r3l-…-no-leg-fill.stl` | same bear without the leg block | 82 x 63 mm | 1.9 % | if you prefer daylight between the legs; red is the crotch |
| `bear-r3h-one-arm-up-sky-roar-on-rock-160mm.stl` | round 3: one arm up, one down, roaring at the sky, rock plinth, leg fill | 92 x 63 mm | 0.8 % | clay-style face, asymmetric pose |
| `bear-r3k-bronze-sky-roar-160mm.stl` | round 3, bronze: both arms up roaring at the sky, no plinth, leg fill | 94 x 67 mm | 1.0 % | the fierce one without a rock |
| `bear-r3b-sky-roar-on-rock-160mm.stl` | round 3: both arms up roaring at the sky, rock plinth, leg fill | 85 x 70 mm | 1.5 % | clay-style symmetric alternative |
| `bear-r3d-boxer-guard-on-rock-160mm.stl` | round 3: elbows tucked, forearms vertical, jaw closed, rock plinth, leg fill | 96 x 85 mm | 3.2 % | calmest pose |
| `bear-c-one-paw-raised-160mm.stl` | one paw raised, other arm down, mouth open | 90 x 84 mm | **5.2 %** | **recommended** — most sculptural and least support |
| `bear-o-paws-tucked-jaw-closed-160mm.stl` | paws at chest, jaw closed | 82 x 94 mm | 6.3 % | calmest; no jaw overhang |
| `bear-o-…-100mm-QUICK-TEST.stl` | same, 100 mm | 53 x 60 mm | 6.2 % | ~1 h print to test glow / wall thickness |
| `bear-m-tall-totem-arms-down-160mm.stl` | tall, arms at the sides, frontal | see preview | low | the "totem pole" shape |
| `bear-k-swipe-head-turned-160mm.stl` | both paws forward, head turned | 86 x 96 mm | 7.6 % | forearm undersides need support |
| `bear-d-classic-spread-arm-roar-160mm.stl` | spread arms, roaring (round-1 reference) | 143 x 66 mm | 6.3 % | the widest; underarms + crotch |

`preview-bear-<id>.png` beside each file shows six views with the faces that
need support in red.

**Slicer settings (Centauri Carbon 2, 0.6 mm hardened nozzle, strontium-aluminate
filament):** 2 walls (1.2 mm), 0 % infill, **0 bottom layers**, normal top layers,
0.2 mm layers, tree supports only (45° threshold matches the red areas), brim on.

Provenance: the letter in each name is the Stage-1 candidate id
(`outputs/stage1_refs/round2z/sheet.png`); the raw reconstruction and cutout are
in `outputs/stage2_mesh/round2z/<id>.glb` / `<id>_cutout.png`; the repair log is
what `tools/mesh_repair.py` prints. See `PIPELINE.md` and `APPROACH.md`.
