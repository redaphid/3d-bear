# print-ready — files you can drop straight into the slicer

**Status 2026-09-10 02:30:** none of these is the final bear yet — the user's verdict is that they are
not fierce or grizzly enough; round 4 (`blueprints/stage1_refs_round4z.yaml`) is running for identity.

Every STL here is a validated solid (watertight, consistent winding, Euler 2,
manifold3d clean). Round-3 files use the recipe from `outputs/stage3_print/quality/report.md`:
0.4 mm voxel pitch at iso 0.7 (0.05 mm mean surface error), Taubin-smoothed, 25k faces. No fill between
the legs (a block there was rejected as a wall). Older files are 0.6 mm / 12k faces. All are scaled so
the **printed piece is the height in the filename**, with the bottom 8 mm cut
away so the base is open for the light and the pole.

| file | pose | footprint | needs support | notes |
|---|---|---|---|---|
| `bear-r3l-bronze-sky-roar-on-rock-160mm.stl` | round 3, bronze: grizzly anatomy, both arms up roaring at the sky, rock plinth | 82 x 63 mm | 1.90 % | lowest support; smoothed 25k faces; red is the crotch only |
| `bear-r3h-one-arm-up-sky-roar-on-rock-160mm.stl` | round 3: one arm up, one down, roaring at the sky, rock plinth | 92 x 63 mm | 1.89 % | clay-style face, asymmetric pose |
| `bear-r3k-bronze-sky-roar-160mm.stl` | round 3, bronze: both arms up roaring at the sky, no plinth | 94 x 67 mm | 3.12 % | the fierce-ish one without a rock |
| `bear-r3b-sky-roar-on-rock-160mm.stl` | round 3: both arms up roaring at the sky, rock plinth | 85 x 70 mm | 2.72 % | clay-style symmetric alternative |
| `bear-r3d-boxer-guard-on-rock-160mm.stl` | round 3: elbows tucked, forearms vertical, jaw closed, rock plinth | 96 x 85 mm | 4.48 % | calmest pose |
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
