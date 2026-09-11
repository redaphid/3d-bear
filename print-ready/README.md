# print-ready — files you can drop straight into the slicer

**Status 2026-09-10 14:00:** the user chose round-4 `b`, now reconstructed with **TRELLIS.2** instead of Hunyuan3D —
it carries the carved fur Hunyuan flattened away. Print `bear-r4b-TRELLIS-grizzly-roar-on-rock-160mm.stl`.
Evidence and the environment build are in `docs/TRELLIS2_EVAL.md`.

Every STL here is a validated solid (watertight, consistent winding, Euler 2,
manifold3d clean). Round-3 files use the recipe from `outputs/stage3_print/quality/report.md`:
0.4 mm voxel pitch at iso 0.7 (0.05 mm mean surface error), Taubin-smoothed, 25k faces. No fill between
the legs (a block there was rejected as a wall). Older files are 0.6 mm / 12k faces. All are scaled so
the **printed piece is the height in the filename**, with the bottom 8 mm cut
away so the base is open for the light and the pole.

| file | pose | footprint | needs support | notes |
|---|---|---|---|---|
| `keychain-bear-r4b-TRELLIS-32mm-corded.stl` | **keychain, for a 1 mm stretch cord**: the bear at 20 % (32 mm) with a 3 mm tunnel bored side-to-side through the **skull only** (86 % height), exiting into the 2 mm gaps between head and raised arms — no added loop, nothing through the arms | 19 x 17 mm | 4.4 % | **RECOMMENDED.** 2.4 mm of skull above the tunnel; thread with a needle through the gap. Hole prints ~0.5 mm undersized |
| `keychain-bear-r4b-TRELLIS-32mm-side.stl` | ring version, 4.5 mm hole sized for a key ring rather than a cord | 19 x 17 mm | n/a | print SOLID, no supports. Ring section 14 mm2, about twice the 2.2 mm version |
| `keychain-bear-r4b-TRELLIS-32mm-front.stl` | same, hole facing front (hangs as a pendant) | 19 x 17 mm | n/a | same ring |
| `totem-bear-r4b-TRELLIS-240mm-hollow-2.5mm.stl` | the same totem at **240 mm** (fills the Centauri's 256 mm cube with margin), 2.5 mm wall, base opening 134 x 129 mm | 143 x 129 mm | 8.8 % incl. cavity ceilings | the large option: ~215 cm3, about 267 g; same slicing notes |
| `totem-bear-r4b-TRELLIS-160mm-hollow-2mm.stl` | **THE TOTEM**: the chosen bear at 160 mm, **modelled hollow with a uniform 2.0 mm wall**, base open through the plinth (89 x 87 mm) for the pole and the light, no ring | 97 x 87 mm | 9.1 % incl. the cavity ceilings (3.7 % outside) | **PRINT THIS for Goldrush.** ~78 cm3 of material, about 97 g. Slice as a normal solid (3 walls, any infill is irrelevant — it is already a shell); let tree supports grow inside through the base opening or accept sag on the hidden ceilings |
| `bear-r4b-TRELLIS-grizzly-roar-on-rock-160mm.stl` | **round 4 bear b via TRELLIS.2 dual-contouring**: carved fur on arms and shoulders, open jaw with tongue and teeth, separate claws, rock plinth | 96 x 86 mm | **3.7 %** | the solid it was hollowed from (use this only if you want the slicer to do the hollowing: 2 walls, 0 % infill, 0 bottom layers) |
| `bear-r4b-grizzly-roar-arms-up-on-rock-160mm.stl` | the same bear via Hunyuan3D 2.1 — same pose, smooth surface, no fur | 94 x 71 mm | 3.0 % | superseded by the TRELLIS version above |
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
