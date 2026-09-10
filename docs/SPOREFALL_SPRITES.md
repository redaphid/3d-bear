# Sporefall sprite sheets with the bear pipeline

*How the method built for the Goldrush grizzly (`../APPROACH.md`, `../PIPELINE.md`)
could produce the animated character sprites Sporefall Station actually consumes —
and one thing the bear proved that the existing sprite pipeline has been missing.*

Written 2026-09-10 from three sources on this machine: `D:\Projects\sporefall-station`
(the game — its `docs/themes.md` is the sprite contract), `D:\Projects\sporefall-art`
(the existing concept-art → Wan 2.2 Animate → pixelize pipeline, last active
2026-08-23), and what the bear pipeline measured overnight. Nothing here is
implemented; it is a proposal with a first experiment at the end.

---

## 1. What the game needs (the contract, verbatim from `docs/themes.md`)

| Property | Value |
|---|---|
| Character cell | **48 px** drawn (`artScale: 2` in `swampspace-hires` → author at 96 px) |
| Drawn directions | **5**: `s se e ne n`. The west half (`sw w nw`) is the **east art mirrored by the engine** — never drawn |
| Animation states | `idle walk attack hurt roll death`, **up to 8 frames each**, contiguous from 0 |
| Key grammar | `char.<name>.<dir>-<state>-<n>` → one PNG per frame, listed in `manifest.json`. **No atlas.** The engine wants individual frames and a manifest, not a packed sheet |
| Cadence | sim ticks per frame (30 ticks = 1 s): idle 12 · walk 6 · attack 2 · hurt 3 · roll 3 · death 5 → **2.5 / 5 / 15 / 10 / 10 / 6 fps**, overridable per state in the manifest `anim` block |
| Fallbacks | a missing direction borrows a neighbour (`se→s`, `e→s`, `ne→e→s`, `n→s`); a missing state falls back down `death > roll > hurt > attack > walk > idle`. **Shipping a partial set is fine and renders correctly** |
| Cast | six archetypes in the shipped theme: `player` = vine-ranger, `thug` = bog-mutant, `scientist` = mycologist, `shopkeeper` = frog-settler, `sporeling`/drone = spore-drone, `robot` = derelict-bot. The shipped art is "bad placeholder — matching it is NOT a goal" (sporefall-art SESSION_LOG, 2026-07-25) |

Full set, if everything were drawn: 6 characters × 5 directions × ~26 frames
(idle 1 + walk 8 + attack 4 + hurt 3 + roll 4 + death 6) ≈ **780 frames**. The
fallback rules mean the useful order is *idle + walk for everyone first*, then
attack for the player, then the rest.

Two consequences the current sprite pipeline doesn't yet reflect:

- `sprites/pack.py`'s atlas (stage 4 in sporefall-art's CLAUDE.md) is a preview
  artefact. The deliverable is `chars/<name>-<dir>-<state>-<n>.png` + a manifest
  fragment. That "stage 4" is a 40-line emitter, not a packer.
- Frame counts are small and cadences are slow. A 77-frame Wan clip at 16 fps
  is ~5 s of motion; a walk cycle needs **8 frames at 5 fps** from it. Most of
  what Wan generates is discarded — which is fine, but it means the expensive
  step is being spent on temporal smoothness the game never shows.

## 2. What sporefall-art already has, and where it hurt

`sprites/make_sprite.py` is glue over five real modules:

```
motion.py        HY-Motion takes (ComfyUI) or Mixamo FBX → measured in Blender → winner cast
run_wan_prep.py  dense mannequin render (Blender render_clip.py, ONE direction) → driving mp4
run_wan_animate  reference crop + DWPose(driving) → WanAnimateToVideo → 77 frames @16fps
judge.py         metrics + PASS/FAIL gates + contact/head/worst-pair sheets
pixelize.py      k-centroid downscale + frozen master palette + synthesized shadow
pack.py          webp at game fps + atlas (+ pack_sheet_8way)
```

Its own logs record the pain, and every item is one the bear pipeline hit too:

| sporefall-art finding (HANDOFF / SESSION_LOG) | bear pipeline equivalent (APPROACH §3) |
|---|---|
| fp8 Wan Animate UNET (18 GB) thrashes VRAM, 60–70 min/clip; GGUF Q5 is 2–10 min | Qwen 20 GB thrashed to 1 img/45 min; anything > ~15 GB shared with Ollama streams weights |
| ComfyUI wedges in a state `/interrupt` won't clear; only a restart clears it | `/interrupt` never reaches a streaming step or a VAE decode; kill + relaunch |
| `/queue` is not a liveness signal | same — watch the websocket / `/history` / the output dir |
| model thrash from interleaved batches; phased by model stack | group jobs by model family, `POST /free` at every switch, one queue manager |
| per-frame SDXL img2img is dead for identity; Wan Animate holds it | (n/a — but the 3D route below holds identity *by construction*) |
| "Ollama was NOT the VRAM problem" (2026-07) | it **was** on 2026-09-10: `qwen3:4b` + `bge-m3` pinned 6.2 GB under a SYSTEM supervisor task. Check `ollama ps` before blaming the model |
| turnaround sheet bug: Wan needs ONE figure per reference | the bear's Stage-1 gate — one whole subject, margin, plain background — is the same rule |
| one driving video = one direction; identity drifts between directions | **this is the gap** — see §4 |

The judge is the most valuable thing in that repo: it already turns "is this
good enough" into gates. Keep it; make it the ranking function on a contact sheet.

## 3. What the bear method adds — mapped onto the sprite stages

The bear pipeline is a *method*, not a set of bear-specific graphs. Each row is a
thing that exists and works in `3d-bear` today.

| Method | Applied to sprites |
|---|---|
| **Fragments are functions.** `decompose` a working graph into a typed fragment; blueprints wire them; compose is the compiler | `run_wan_animate.graph()` builds its graph in Python. Decompose that JSON once into `fragments/wan_animate.json` (inputs: `reference: IMAGE`, `driving: VIDEO`; params: `cfg`, `steps`, `length`, `lora`, `gguf`). Likewise `dwpose`, `rembg`, `prompt_builder`, `tap_image`. The Python glue becomes a blueprint |
| **Every stage is a sweep.** ~20 candidates, labelled contact sheet, pick by id | 20 concept candidates per character (Z-Image, 33 s each); 5–10 motion takes per action; 3 seeds per Wan clip. `judge.py` ranks the sheet instead of a human scrolling a gallery |
| **In-graph prompt builder** over a matrix | `subject · action · style` from `sprites/prompts.py` `CHARACTERS` becomes `StringConcatenate` nodes — the prompt is visible in the graph, per item |
| **Debug taps, bypassed by default** (`debug/` prefix, stripped by `tools/build.py` unless `--debug`) | taps on: the DWPose skeleton overlay, raw Wan frames pre-pixelize, pre-palette frames. On by default for a new character's first run, off for batch |
| **Outputs are a library.** Every PNG/GLB carries its API prompt; `outputs/<stage>/<round>/index.md` | `D:\sync\Comfy\sporefall\<stage>\<round>\<char>\…` — drag any frame onto the canvas to get back the exact graph that made it. Replaces `NIGHT_LOG`-style archaeology |
| **GPU never idles, never thrashes; nobody waits for a human** | one queue-manager agent: family grouping (Wan GGUF / Z-Image / Hunyuan3D), `/free` at switches, stall detection with kill + relaunch, arrivals streamed to chat as files land |
| **Delegate; main session steers** | already a rule in sporefall-art's CLAUDE.md ("THE MAIN SESSION DELEGATES") — the bear run used sweep / stage / mesh / queue agents with disjoint file ownership and one committer |
| **Watchable** (`--preview-method auto`, running graph on the canvas, grouped layout) | the same server flag applies; Wan previews are more fun than bears |

## 4. The thing the bear proved: a mesh solves direction consistency

Sporefall needs the *same* character from five directions. sporefall-art gets each
direction from a separate Wan clip driven by a grey mannequin rendered from that
direction, conditioned on **one front-view reference**. Identity holds within a
clip (Wan Animate's strength) but nothing ties the `ne` clip's face to the `s`
clip's face except the same front reference — which is the wrong view for four of
the five directions.

Overnight, Hunyuan3D 2.1 turned a single **frontal** reference of the bear into a
mesh with a convincing back, shoulders and rump in 66 s (`outputs/scratch/
mesh_round1_d_views.png`), and `tools/mesh_repair.py` made it a validated solid in
8 s. A concept image is one minute from being a rotatable object. That gives two
routes, in increasing ambition:

**Route A — mesh as turnaround generator (minimal new tooling, fixes the gap).**
Concept → `rembg` → `hy3d_i2m` → repaired mesh → Blender renders the *static*
character from `s se e ne n` at the game's camera elevation (sporefall-art already
has `blender_scripts/render_clip.py` and the camera conventions) → five reference
images that are the same object from the right angle. Then the existing Wan
Animate stage runs per direction **with the matching view as its reference**
instead of the front crop. Everything downstream (judge, pixelize, manifest) is
unchanged. Cost: one Hunyuan3D job per character, five renders, zero rigging.

**Route B — mesh replaces the mannequin (identity by construction).**
Rig the character mesh (Mixamo auto-rig upload, or Rigify in Blender — both work
on a watertight biped; the voxel remesh guarantees watertight) and drive it with
the motion library sporefall-art already casts (`motion.py`: HY-Motion takes,
Mixamo FBX). Render the animated character itself from the five directions:

- *B1, direct:* shade the mesh (Hunyuan3D-Paint 2.0 is on disk for texture, or
  flat toon shading + the master palette) and render final frames. Seconds per
  frame, perfect cross-frame and cross-direction consistency, no Wan at all.
  Weakness: rigid-body "figurine" motion, visible if the concept was painterly.
- *B2, hybrid:* use the rendered character (not a grey mannequin) as **both** the
  driving video and the per-direction reference for Wan Animate. Wan adds the
  painterly surface and secondary motion; identity and silhouette are pinned by
  the render. Best of both, one extra render per clip.

Route A is an evening. Route B1 is the fastest way to a *complete* 780-frame set.
B2 is what to do once A shows the per-direction references help the judge scores.

## 5. Proposed stages and sweep matrix

```
S1 concept     Z-Image Turbo, CLIP on CPU (33 s/img, 12.7 GB)     20/character → sheet → pick
S2 mesh        rembg → Hunyuan3D 2.1 (66 s) → mesh_repair (8 s)   all 20 → six-view sheets → pick
S3 turnaround  Blender ortho render, 5 dirs, game elevation       seconds; taps: silhouette mask
S4 motion      existing motion library (HY-Motion / Mixamo)       reuse; sweep takes if needed
S5 animate     Wan 2.2 Animate GGUF, ref = S3 view for that dir   (char × dir × state) × 3 seeds
S6 frames      judge → pick seed → resample to cadence → pixelize (existing) → palette lock
S7 emit        chars/<name>-<dir>-<state>-<n>.png + manifest fragment → load with ?theme=
```

Sweep dimensions and the gate each is judged on:

| Stage | Vary | Judge by |
|---|---|---|
| S1 | style suffix (`$var`), pose, seed; the bear's *geometric* view language ("body rotated ~45°, near shoulder forward") — keep poses **asymmetric**: raised symmetric arms pulled Z-Image frontal in 7 of 7 cases | single figure, plain background, margin, no shadow, silhouette readable at 48 px |
| S2 | octree 256/384, seed | watertight after repair, back plausibility on the six-view sheet, % overhang irrelevant here — but limb separation matters (fused arms = fused sprites) |
| S3 | camera elevation, mirror check (`e` vs mirrored `w` must match the game) | one direction per image, consistent scale (`px_per_unit`) |
| S5 | seed ×3, cfg 2.5 / steps 8 (GGUF), `length` | `judge.py` gates: identity strobing (head strip), worst consecutive pair, coherence |
| S6 | k-centroid cell, palette size | palette conformance, alpha cleanliness, silhouette stability at cadence |

GPU budget, honest: Wan GGUF at 2–10 min/clip × (6 chars × 5 dirs × 6 states) =
180 clips ≈ 6–30 h. Do it in priority order and ship partial sets — the engine's
fallback chains exist for exactly this. Route B1 renders the same 780 frames in
minutes on the CPU after one rig per character, which is why it is worth an
experiment even if B2 is the eventual look.

## 6. Repo layout, if this lands in sporefall-art

```
sporefall-art/
  comfy.yaml           project/1: defaults.where local, vars: {style, negative, palette…}
  fragments/           t2i_zimage, prompt_builder, rembg, hy3d_i2m, dwpose, wan_animate, tap_image
  blueprints/          s1_concepts.yaml  s2_mesh.yaml  s5_animate.yaml  (foreach + chunk)
  tools/               build.py (from 3d-bear), push_assets.py, collect.py, queue_*.py,
                       mesh_repair.py / mesh_views.py (from 3d-bear), turnaround.py (Blender),
                       emit_manifest.py (new, ~40 lines)
  sprites/             judge.py, pixelize.py, motion.py stay as post-graph steps
  outputs/<stage>/<round>/<char>/…  + index.md, sheets committed, frames not
```

Copy, don't reinvent: `tools/build.py`, `push_assets.py`, `collect.py`,
`mesh_repair.py`, `mesh_views.py` and the tap fragments are character-agnostic.

## 7. Machine facts that apply unchanged

From `APPROACH.md` §3, all measured on this box:

- ComfyUI must be launched with `--preview-method auto` to see previews; there is no UI toggle.
- Anything that needs > ~15 GB VRAM must own the card: shut Ollama down
  (`Stop-ScheduledTask OllamaProxySupervisor` + elevated `Stop-Process`) or force
  text encoders to CPU (`CLIPLoader device: cpu`).
- `/interrupt` cannot stop a streaming step or a VAE decode. Kill and relaunch;
  keep compiled workflows so the queue is trivially resubmitted.
- `comfy assets push` crashes on Windows after uploading; `tools/push_assets.py`
  rescues the lock.
- GLB is Y-up; Blender is Z-up. `mesh_repair.py --up auto` handles it; a Blender
  import of a raw Hunyuan3D GLB will lie on its back.
- System commit, not just VRAM, is the crash: a 62 GB WSL VM plus a streaming
  model hit the limit. Watch `commit used` when Docker Desktop is running.

## 8. First experiment (one evening, Route A on the player)

1. `s1_concepts.yaml`: 20 vine-ranger concepts on Z-Image (CPU encoder), the
   `prompts.py` appearance as `$var.subject`, asymmetric poses, plain grey.
   Pick one from the sheet. (~12 min)
2. `s2_mesh.yaml`: the pick → rembg → Hunyuan3D → `mesh_repair.py --faces 12000`
   → `mesh_views.py`. Confirm the back and the limb separation. (~2 min)
3. `tools/turnaround.py`: Blender, orthographic, the game's elevation, five
   directions, 96 px cell, alpha. Check `e` mirrored equals what the engine
   draws for `w`. (~10 min to write, seconds to run)
4. Existing `run_wan_prep` for `idle` in the five directions; `s5_animate.yaml`
   with `reference = $asset.turnaround/<dir>.png` per item, 3 seeds, `--debug`
   taps on the DWPose overlay. Judge, pick. (5 dirs × 3 seeds × ~4 min ≈ 1 h GPU,
   unattended)
5. `pixelize` → `emit_manifest.py` → drop into `public/themes/swampspace-hires/
   chars/` → `pnpm run dev` → `?theme=swampspace-hires`. Walk in eight directions.

Success criterion: the judge's head-strip identity score for `ne`/`n` is no worse
than for `s`, and the character looks like one creature while turning. If it does,
the per-direction reference is the fix and Route B2 is next; if it doesn't, the
mesh renders themselves (B1) are the fallback that cannot drift.

## 9. Open questions

- Rigging a generated mesh: Mixamo's auto-rigger wants a T/A-pose; Hunyuan3D
  reproduces whatever pose the concept had. Either generate concepts in A-pose
  (a `$var`), or accept Route A only until an auto-rigger that handles arbitrary
  poses is verified locally.
- Isometric vs top-down: sporefall-art calls its output "isometric", the station
  is top-down with billboards. The turnaround camera elevation must match what
  the shipped `chars/` were drawn at — measure it from an existing frame before
  rendering 780 new ones.
- Whether Wan Animate GGUF accepts a 96 px-scale reference well, or whether
  references should stay ~512 px and be pixelized after (almost certainly the
  latter; `pixelize.py` assumes it).
- Hunyuan3D-Paint for texture is on disk but unexercised; B1 may be fine with
  toon shading + the frozen palette, which also sidesteps texture seams.
