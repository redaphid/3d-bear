# HANDOFF — generating the Goldrush grizzly with ComfyUI

**Status:** scaffolding built and Stage 1 sweeping — read `PIPELINE.md` for
how to build, run, debug and extend the flows. TRELLIS 2 is still absent from
this ComfyUI (0.31.0), so Stage 2 runs Hunyuan3D 2.1 (`blueprints/stage2_mesh.yaml`).
**Written:** 2026-09-10. **Goldrush:** 2026-09-12.
**Owner:** Aaron (@redaphid)

---

## What we're making

A rearing grizzly bear, printed hollow in strontium-aluminate filament, lit
from inside with a blacklight, mounted on a pole. A totem for Goldrush.

The bear is the part that isn't solved. Everything downstream of the mesh —
hollowing, slicing, printing, lighting — is understood and is documented at
the bottom of this file. Read that section first if you only have ten
minutes, because it constrains what the mesh has to be.

## Why we're generating instead of downloading

Three routes were considered and two were closed:

| Route | Outcome |
|---|---|
| Parametric mesh from code | Attempted 2026-09-10. Produced a watertight, support-free, printable bear that read as a chess piece. Mechanically sound, aesthetically dead. Script kept for the printability checks it carries, not the geometry. |
| Download from a repository | Best candidate was a 16cm low-poly rearing bear on MakerWorld. Not free, and its Standard Digital File License forbids derivatives and redistribution — which collides with hollowing it *and* with this being a git repo that pushes to GitHub. |
| **Generate locally in ComfyUI** | **This document.** Output is ours, commits cleanly to the repo, no license to violate. |

The license point matters more than it looks. `.gitignore` here is a stock
Node one with no model-file patterns, and `LICENSE.md` says MIT. Dropping a
third-party STL in this directory and running `git add -A` would publish
someone else's model under a license that isn't ours to grant. A generated
mesh has no such problem — which is most of why we're here.

---

## Pipeline

Four stages. Each one has a gate: don't proceed until the gate passes,
because every stage amplifies the errors of the one before it.

```
reference images  →  image-to-3D  →  printable mesh  →  sliced glowing bear
   (stage 1)          (stage 2)        (stage 3)           (stage 4)
```

### Stage 1 — reference images

This stage decides the quality of everything downstream. Reconstruction
models are extremely sensitive to the input image, and far more people fail
here than at stage 2.

Generate a rearing grizzly with whatever image model is loaded. Requirements
on the output, in rough order of how much they matter:

- **Plain, flat background.** Mid-grey or white. No scene, no environment.
- **Even, diffuse lighting. No cast shadows.** Reconstruction bakes shading
  into geometry — a hard shadow under the jaw becomes a dent in the jaw.
- **The whole animal, uncropped**, with margin on all sides. A paw touching
  the frame edge becomes a paw fused to nothing.
- **Neutral colour, low contrast fur detail.** Detail you can see is detail
  the model will try to build, and every bit of it is a place for the print
  to fail. You want the silhouette, not the pelt.
- **Three-quarter front view** as the primary. If going multi-view (see
  stage 2), also produce front, left side, and back — *of the same animal in
  the same pose*, which is the hard part.

Prompt sketch — adapt, don't paste:

> full body grizzly bear rearing on hind legs, forelegs raised, mouth open
> roaring, three-quarter front view, plain flat neutral grey background,
> soft even studio lighting, no shadows, matte clay material, simplified
> smooth forms, sculptural, full figure in frame with margin

Adding `matte clay` / `sculptural` / `simplified` earns its place: it
suppresses fur texture and specular highlights, both of which reconstruct
badly.

**Gate:** you can see the whole bear, the background is empty, nothing is
cropped, and there are no dark shadows. If not, regenerate. This is cheap;
stage 2 is not.

### Stage 2 — image to 3D

Two backends, both live in ComfyUI as of this writing. Verify what's
actually installed before planning around either.

Picking on geometry quality, not on convenience. Texture is irrelevant here —
we print in one filament and the object supplies its own colour by glowing —
so the only axes that matter are **how clean the mesh is** and **whether it
comes out watertight.** Most published comparisons rank these models on speed,
cost and texture fidelity, which is the wrong leaderboard for us.

### The pick: TRELLIS 2

Native in ComfyUI core since 2026-08-22 — not a partner node, not an API, no
per-generation billing. Local weights, INT8 or bf16.

The deciding argument is not the generator, it's what ships with it. The core
integration includes a complete mesh post-processing chain reimplemented in
PyTorch/scipy with no extra dependencies: **DC remesh, QEM decimation, UV
unwrap**. Dual-contouring remesh produces closed manifold surfaces, and
watertightness is *the* failure mode of generated meshes — it's the thing
stage 3 exists to fix. TRELLIS 2 does it inside the graph. QEM decimation is
also exactly the "decimate deliberately" step stage 3 calls for, so a chunk
of that stage collapses into the same workflow.

It's also described as strong on sharp features and complex topology, which
suits a faceted sculptural bear better than a model tuned for smooth
photoreal props.

**Prerequisite — your ComfyUI needs updating.** The running instance reports
0.31.0 and registers **zero** TRELLIS nodes. Since this support ships in core
rather than a custom pack, that means the version predates it. Update first;
the download list below is useless until the nodes exist.

Files → `D:\comfyshared\ComfyModels\`:

| File | Into |
|---|---|
| `trellis_2_int8_convrot.safetensors` | `diffusion_models/` |
| `pixal3d_int8_convrot.safetensors` | `diffusion_models/` |
| `trellis_2_shape_vae_bf16.safetensors` | `vae/` |
| `trellis_2_texture_vae_bf16.safetensors` | `vae/` |
| `dino_v3_L_naf_fp32.safetensors` | `clip_vision/` |
| `birefnet.safetensors` | `background_removal/` |

### Free A/B: Pixal3D

Ships in the same workflow — the template carries a `Boolean (Switch to
Trellis2)` node, `false` loads Pixal3D instead. Same encoders, same VAEs, only
the diffusion model and conditioning differ, and you're downloading its
weights anyway in the table above. So it costs one toggle to compare.

Worth comparing, worth being suspicious of: it claims near-reconstruction
fidelity from a single image, but independent comparison reports mesh
artifacts that the other two models don't produce. On a piece that has to
print, artifacts are disqualifying in a way they aren't for a render.

### Baseline: Hunyuan3D 2.1 (already on disk)

`hunyuan_3d_v2.1.safetensors`, nodes present, zero setup. Run it on the same
reference image as your control. If it produces a printable bear before you've
finished updating ComfyUI, that is a legitimate outcome and not a compromise —
2.1 is a capable model and the bear only has to survive a festival.

Chain: image → `Hunyuan3Dv2Conditioning` → sampler → `VAEDecodeHunyuan3D` →
`VoxelToMesh` → `SaveGLB`. Remove the background first. Skip texture.

The multi-view checkpoint (`hunyuan3d-dit-v2-mv.safetensors`) is not on disk;
the node is. Only fetch it if the back or the raised forelegs come out wrong.

### Deliberately not using

**Hunyuan3D 3.0.** On paper it's the strongest of the lot — 1024 geometry
resolution, clean topology, 2–4 image multi-view. But in ComfyUI it's exposed
through **Partner Nodes**, which are cloud API calls billed per generation.
Given you've already flagged that cost is real, this is the same trap as the
`Tripo*`, `Meshy*` and `Rodin3D*` nodes: they look local in the node search
and they are not. (`TripoSR\model.ckpt` on your disk is genuinely local and
unrelated to the `Tripo*Node` family.)

**Sparc3D 2.0.** The one model rated explicitly for watertight meshes and 3D
printing, with polycount control to 2M faces — on the axis we actually care
about, it's the best-reviewed thing out there. I can only find a paper, a
project page and a HuggingFace *Space* (a hosted demo). No weights repo, no
ComfyUI node. Watch it; can't run it tonight. If you find local weights, it
displaces TRELLIS 2 as the pick.

**Gate:** the mesh looks like a rearing bear from all sides in
`Preview3DAdvanced`. Rotate it. The back and the raised forelegs are where
reconstruction fails, and they're the two things you cannot see in your
reference image.

### Stage 3 — making it printable

Generated meshes are never print-ready. They arrive dense, frequently
non-manifold, sometimes with internal geometry, and always in the wrong
units. Budget real time here.

1. **Convert and inspect.** `.glb` → `.stl`. `check_mesh.py` in this repo
   reports watertightness, winding, volume, footprint, height, and — the one
   that actually matters — an area-weighted census of every downward-facing
   surface steeper than 45°. **GLB is Y-up**; `check_mesh.py --up auto`
   rotates it (default for `.glb`). First bear at 160 mm: 136 × 63 mm
   footprint, 8.6 % of surface needing support — well inside the Centauri.
   `tools/mesh_views.py` renders six labelled views to one PNG for judging.
2. **Repair if not watertight — by volumetric remesh, not hole-filling.**
   Nothing downstream is trustworthy until it is. Measured on the first
   Hunyuan3D 2.1 output (2026-09-10): one connected body, ~180 boundary
   loops, ~873 tiny debris shells, high Euler number — non-manifold edges
   shared by more than two faces, the signature of marching-cubes extraction
   with self-intersections. Hole-filling cannot repair that by construction
   (`trimesh.fill_holes` did nothing). The fix is to **voxelize to a solid and
   re-extract the surface**, which is watertight by definition:
   `tools/mesh_repair.py <in.glb> --out <out.stl> --height 160 --open-base`
   (keeps the largest component, voxelizes at ~0.6 mm, re-extracts,
   validates with `manifold3d`, decimates, scales, opens the base). This is
   also the argument for TRELLIS 2 once ComfyUI is updated — its DC remesh
   does exactly this inside the graph.
3. **Decimate, deliberately.** Reconstruction output runs to hundreds of
   thousands of triangles. Decimating hard doesn't just slice faster — it
   *is* the low-poly aesthetic, and flat facets catch UV at different angles
   and read better in the dark than a smooth surface does. Target somewhere
   in the low thousands and look at it.
4. **Scale.** 16cm tall is the reference point; it fits the Centauri with
   room and prints in a few hours. Taller is a better totem and a worse bet
   against the clock.
5. **Re-run the overhang check.** A roaring open jaw and raised forelegs
   will have unsupported surface. You want to know how much and where before
   the slicer tells you.
6. **Open the base.** The light and the pole both enter from underneath. If
   the feet are separate islands rather than one opening, cut a cavity —
   this is the one place a boolean is worth writing by hand.

**Gate:** watertight, under ~5% unsupported surface, correct height, one
usable opening at the bottom.

### Stage 4 — hollow, slice, print

Settings for **Centauri Carbon 2, 0.6mm hardened steel nozzle, strontium
aluminate filament** (hardened is mandatory — the filament is ceramic and
eats brass):

| Setting | Value | Why |
|---|---|---|
| Walls | 2 (= 1.2mm) | The one variable that decides brightness. See below. |
| Infill | 0% | It's a lantern. |
| Bottom layers | 0 | Open base — light and pole enter here. |
| Top layers | normal | The shell has to close over the head. |
| Layer height | 0.2mm | Or 0.16 for finer facet edges, at a time cost. |
| Supports | tree, only where the check says | Every support scar is a dull patch under UV. |
| Brim | yes | Cheap insurance on a printer that's been misbehaving. |

**On wall thickness.** Strontium aluminate is not a diffuser — it's loaded
with ceramic and it's fairly opaque. A blacklight inside mostly charges the
*inner* surface, and what you see outside is what bleeds through the wall.
Past roughly 1.2mm you are lighting the inside of the bear for the bear's
benefit. 2 walls at 0.6mm sits right at that edge.

Settle this empirically before committing hours of filament: print a
stepped test coupon — vertical fins at 0.6 / 0.9 / 1.2 / 1.5 / 1.8 / 2.4mm —
charge it, and take it into a dark room. Fifteen minutes to answer a
question that otherwise costs a whole print. `ladder.stl` in this repo is
that coupon.

**Gate:** it glows, at a distance, in the dark, from the outside.

---

## Known ways this goes wrong

- **The printer.** It's been throwing multiple faults and was mid-
  calibration on 2026-09-10. At ~3h a print you get roughly three attempts
  before Goldrush. Spending two of them on the same undiagnosed fault is the
  real risk here — more than the model, more than the mesh. If one fails,
  diagnose before reprinting.
- **Reconstruction hallucinates backs.** Whatever the reference image
  doesn't show, the model invents. Raised forelegs and the far side of the
  head are the usual casualties.
- **Support scarring reads as dead patches** under UV, not as rough
  texture. Orientation is worth more thought than usual.
- **Shadows become geometry.** Restated because it's the single most common
  stage-1 mistake.
- **Cost of certainty.** If the clock wins, buying the MakerWorld model is
  the fallback. It's proven, it prints, and it stays out of this repo.

## Verified on `soul`, 2026-09-10

Measured against the live instance on port 8188 rather than assumed:

| Thing | Finding |
|---|---|
| GPU | RTX 4090, 24GB VRAM, ~24GB free |
| System RAM | 137GB |
| ComfyUI | 0.31.0, PyTorch 2.13.0+cu130, Python 3.12.13 |
| Hunyuan3D nodes | present and native |
| Hunyuan3D weights | `hunyuan_3d_v2.1.safetensors` + full diffusers Hunyuan3D-2 tree |
| Multi-view checkpoint | **absent** — `hunyuan3d-dit-v2-mv.safetensors` not on disk |
| TRELLIS / Pixal3D | **absent** — no nodes registered, so core predates the 2026-08-22 release. **Update ComfyUI.** |
| TripoSR | `TripoSR\model.ckpt` present (local) |
| Models dir | `D:\comfyshared\ComfyModels` |
| Output dir | `D:\sync\Comfy` |
| Launch flags | `--fast fp16_accumulation --use-sage-attention --listen=0.0.0.0 --enable-manager` |

The 12GB multi-view VRAM figure that worried this document is a non-issue at
24GB. VRAM was never going to be the constraint; the reference image is.

## Still unverified

- Whether strontium aluminate wants a different first-layer temperature than
  standard PLA on the Centauri.
- Whether the printer's outstanding faults are one problem or several.
- Whether Sparc3D weights are obtainable for local inference. It is the best
  fit on paper for printable geometry and I could only find a hosted demo.
- Whether TRELLIS 2's DC remesh alone gets a mesh past `check_mesh.py`, or
  whether a repair pass is still needed. Measure it; don't assume.

## Prior art worth reading first

`redaphid/3d-modeling-darksouls` — private repo, created 2026-02-24,
described as *"Dark Souls 3D scene: text→image→3D pipeline using ComfyUI +
Hunyuan3D + Blender"*. That is this exact pipeline, already built once.

No conversation transcripts survive for it — the mindmeld archive starts
around 2026-04-25 and the repo predates that — so the repo itself is the
only record. Read it before rebuilding from this document. Whatever is in
there is worth more than anything written here, because it already ran.

## Sources

- Hunyuan3D-2 in ComfyUI — https://docs.comfy.org/tutorials/3d/hunyuan3D-2
- TRELLIS 2 in ComfyUI — https://docs.comfy.org/tutorials/3d/trellis2
- TRELLIS 2 native support announcement — https://comfyui-wiki.com/en/news/2026-08-22-trellis2-pixal3d-native-comfyui
- ComfyUI 3D node index — https://pozzettiandrea.github.io/ComfyUI-3D_nodes_index/
