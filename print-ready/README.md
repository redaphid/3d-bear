# print-ready — files you can drop straight into the slicer

**Status 2026-09-10 15:00.** The user chose round-4 bear `b` (a bronze-style grizzly roaring with both arms up
on a rock plinth), reconstructed with **TRELLIS.2** so the carved fur, teeth and claws survive. Everything
current is cut from one validated solid. Older files are kept below for the record.

## Current

| file | what | footprint | needs support | notes |
|---|---|---|---|---|
| `totem-bear-r4b-TRELLIS-240mm-hollow-2.5mm.stl` | **THE TOTEM.** 240 mm tall, hollow with a uniform 2.5 mm wall, base open through the plinth (133 x 129 mm) for the pole and the light; high-detail build (0.3 mm pitch, 250k-face outer skin) | 143 x 129 mm | 9.89 % incl. the hidden cavity ceilings (~3.7 % outside) | ~194 cm3, about 240 g. Preview + close-up beside it |
| `totem-bear-r4b-TRELLIS-160mm-hollow-2mm.stl` | the same totem at 160 mm (0.3 mm pitch, 250k-face outer skin), 2 mm wall, base opening 89 x 87 mm | 97 x 87 mm | 10.10 % incl. cavity ceilings | high-detail build like the 240; ~64 cm3, about 79 g |
| `keychain-bear-r4b-TRELLIS-32mm-corded.stl` | **the keychain**: the bear at 20 % (32 mm) with a 3 mm tunnel bored through the skull only for a 1 mm stretch cord, exiting into the gaps between head and raised arms; nothing protrudes | 19 x 17 mm | 4.4 % | print SOLID, no supports; the hole prints ~0.5 mm undersized; thread with a needle through the 2 mm gap |
| `bear-r4b-TRELLIS-grizzly-roar-on-rock-160mm.stl` | the validated solid the files above were cut from (46k faces, solid, base cut) | 96 x 86 mm | 3.7 % | use only if you want the slicer to hollow it (2 walls, 0 % infill, 0 bottom layers) |
| `keychain-bear-r4b-TRELLIS-32mm-side.stl`, `…-front.stl` | ring-on-the-head variants (4.5 mm hole, 3 mm tube) sized for a key ring, not a cord | 19 x 17 mm | — | kept as options; the ring is the weak point (14 mm2) |

## How to slice the totem (Centauri Carbon 2, 0.6 mm hardened nozzle, strontium-aluminate filament)

The hollow is modelled, so **slice it as an ordinary solid**: 3 walls (1.8 mm), any infill setting (there is
nothing to fill), normal top and bottom layers, 0.2 mm layers (0.12–0.16 mm if you want the fur crisper),
brim on. Supports: the outside needs tree supports only at the 45° threshold (the red patches in the
preview: inner upper arms, crotch, under the jaw). The cavity ceilings inside the head, arms and the top of
the plinth are real overhangs the slicer cannot see from outside — either let tree supports grow up inside
through the base opening (reachable to remove) or accept sag on surfaces nobody sees. The `…-solid` file
uses the older recipe instead: 2 walls, 0 % infill, **0 bottom layers**.

Keychain: solid (100 % infill or 4+ walls), no supports.

## Superseded (kept for the write-up)

| file | why it was superseded |
|---|---|
| `bear-r4b-grizzly-roar-arms-up-on-rock-160mm.stl` | the same bear via Hunyuan3D — smooth, no face detail (3.0 % support, 94 x 71 mm) |
| `bear-r3l-bronze-sky-roar-on-rock-160mm.stl` (1.9 %), `bear-r3h-…` (1.9 %), `bear-r3b-…` (2.7 %), `bear-r3k-…` (3.1 %), `bear-r3d-…` (4.5 %) | round 3: the pose-engineered bears — lowest support of the project, but roaring at the sky hides the face and the clay ones read as toys |
| `bear-c-one-paw-raised-160mm.stl` (5.2 %), `bear-o-…` (6.3 %), `bear-o-…-100mm-QUICK-TEST.stl`, `bear-m-…`, `bear-k-…` (7.6 %), `bear-d-…` (6.3 %) | rounds 1–2: the first printable bears, all over the 5 % gate |

Every STL here is a validated solid (watertight, consistent winding, manifold3d clean). The letter in each
name is the Stage-1 candidate id; `r3`/`r4` the round; previews are `preview-*.png` with faces needing
support in red. Provenance: `outputs/`, `APPROACH.md`, `PIPELINE.md`.
