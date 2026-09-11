# APPROACH — how we are actually building the bear

**Read `HANDOFF.md` for *what* and *why*. This file is *how we work* and *what we
have learned*, kept current as we go.** `PIPELINE.md` is the reference manual for
the tooling described here.

Session: 2026-09-09/10 (overnight). Goldrush: 2026-09-12. Owner: Aaron (@redaphid).

---

## 1. The working method

Treat the pipeline as a program, not a sequence of manual ComfyUI sessions.

| Idea | How it shows up in the repo |
|---|---|
| **Fragments are functions.** Typed inputs, outputs, named params. | `fragments/*.json` — `t2i_qwen`, `prompt_builder`, `rembg`, `hy3d_i2m`, `tap_image`, `tap_mesh` |
| **Blueprints are programs.** They wire fragments; `foreach` is the loop. | `blueprints/*.yaml` — one per stage/round |
| **Compose is the compiler; compiled JSON is a build artifact.** Never hand-edited. | `*.compiled.json` (git-ignored), built by `tools/build.py` |
| **Every stage is a sweep, not a single shot.** ~20 candidates, contact sheet, pick by id. | `outputs/<stage>/<round>/sheet.png` + `items.json` |
| **Debug taps, bypassed by default.** Intermediate saves exist in the graph and are stripped at build time unless `--debug`. | `filename_prefix` starting `debug/` = tap; `tools/build.py --debug` keeps them; shown purple/bypassed in the UI |
| **Prompts are built in-graph.** `StringConcatenate` chain over `subject · view · pose · mass · mouth · style`, so the variation matrix is visible as nodes. | `fragments/prompt_builder.json`; constants in `comfy.yaml` `vars:` |
| **Outputs are a library.** ComfyUI embeds the API prompt in every PNG and GLB — the output tree *is* a set of re-runnable workflow states. Drag a file onto the canvas to restore the exact graph that made it. | server: `D:\sync\Comfy\3d-bear\<stage>\<round>\<id>…`; project mirror: `outputs/<stage>/<round>/<id>.<ext>` + `index.md` |
| **Watchable.** The running graph is loaded onto the browser canvas with live denoising previews; a grouped, colour-coded layout is generated from the compiled graph. | `tools/ui/` (publishes `bear/<stage>` into the Workflows sidebar) |
| **GPU never idles; nobody waits for a human.** Queue the next informative job behind the current one. Picks happen with full information, not before it exists. | param sweeps and "reconstruct all 20" queued behind the Stage-1 sweep |
| **Slow work is delegated.** Parallel agents own disjoint files; one agent commits. | see §4 |

The gates from `HANDOFF.md` still apply — we just evaluate them on twenty
candidates at once instead of one.

## 2. Decisions so far (and why)

| Decision | Why |
|---|---|
| **Stage 2 runs Hunyuan3D 2.1, not TRELLIS 2.** | The server is ComfyUI 0.31.0 with zero TRELLIS/Pixal3D nodes. Updating ComfyUI three days before the event, on a machine whose printer is already misbehaving, is the wrong risk. HANDOFF explicitly blesses 2.1 as a legitimate outcome. All 2.1 weights are on disk (`hunyuan_3d_v2.1.safetensors`, plus `hunyuan3d-dit-v2-1.fp16.ckpt` / `hunyuan3d-vae-v2-1.fp16.ckpt`). |
| **Stage 1 uses Qwen-Image 2512** (`qwen_image_2512_fp8_e4m3fn` + `qwen_2.5_vl_7b_fp8_scaled` + `qwen_image_vae`). | All three components on disk; strong prompt adherence for a controlled "matte clay on grey" render. Flux dev was the alternative; its checkpoint template wanted separate unet/clip files that aren't all present. |
| **Stage-1 sweeps moved to Z-Image Turbo** (`z_image_turbo_bf16` + `qwen_3_4b` + `ae`, ≈12 GB) after the Qwen stall. | Two `llama-server` processes permanently hold ≈6.2 GB of the 24 GB card, so Qwen-Image 2512 (≈20 GB) streams weights from RAM: 1 image in 45 min, then the box hit its memory commit limit and the session died. Z-Image fits beside them with room to spare and runs 8 steps. Qwen stays available for refining winners if llama-server is stopped. |
| **896² at 20 steps for references** (was 1024² / 50). | Hunyuan3D's vision encoder downsamples the input anyway; round 1 cost ~3.5 min/image for no downstream benefit. |
| **`chunk: 5`** on the 20-item sweep. | Results arrive every ~5 min instead of all at once; the user can steer after the first five. ComfyUI executes FIFO, so chunks keep the GPU saturated. |
| **Background removal (`rembg`) before reconstruction**, with a parallel *no-rembg* control run. | HANDOFF says remove it; we measure whether it matters rather than assume. |
| **Hunyuan3D parameter sweep before picks** (octree 256/384/512, steps 30/50, threshold 0.5/0.7, seeds). | So the settings used for the final bear are chosen from evidence, on a reference we already have. |
| **Reconstruct all 20 references, not just picks.** | GPU time is cheap; a mesh is what we actually choose on. Picking on the image alone hides the "flat back" failure mode. |
| **Round 3z is pose-engineered for the printer** (`blueprints/stage1_refs_round3z.yaml`): arms overhead / boxer's guard / paws clasped under the chin / one up one down / totem column; hind legs pressed together *or* the bear standing on a boulder; head thrown back roaring at the sky, jaw closed, or chin tucked; half clay, half "cast bronze with matte patina". | Round 2z showed support % is a pose question, not a repair one: every red face on every candidate was a horizontal forearm underside, the underside of the muzzle, an armpit or the crotch. The best of 20 was 5.2 %, and the gate for a glow print is < 5 % because every support scar is a dead patch. So the next matrix only contains poses whose downward faces are steep or pressed against the body, adds a boulder that fills the crotch and houses the pole/light, and trials a style that asks for defined anatomy (hump, brow, claws) because the clay style reconstructs as a plush toy. |
| **Everything local.** Not signed into Comfy Cloud; no partner nodes. | No per-generation billing anywhere in the pipeline. |

## 3. What we have learned (measured, not assumed)

**Stage 1**
- Round 1 (4 images, prompt said "three-quarter front view"): **all four came out dead-on frontal.** Qwen centres and symmetrises unless the view is described *geometrically* ("body rotated ~45°, left shoulder nearest the camera, right side recedes") and *early* in the prompt. Round 2's matrix does exactly that — and the one round-2 image that escaped the stall (`d`: R34 · bent · heavy · open) **is a genuine three-quarter view**: body rotated, near shoulder forward, elbows bent, paws in front of the chest. The geometric view language works.
- **Round 2z (Z-Image Turbo, 20 candidates, ~30 s each, 2.5 min per chunk of 5):** every image passes the gates (whole bear, flat grey, shadowless, matte clay, no fur). View adherence: **about 10 of 19 came out genuinely three-quarter** (`c d g i j k o q s`, `h` borderline); `l` and `m` were *asked* to be frontal and were. Every unintended frontal (`a b e f n p t`) is a **raised-arms pose** — symmetric arms pull Z-Image into a symmetric camera; the bent/tall/swipe poses turned as asked. Qwen followed the view clause on its one round-2 image (`d`) but is ~7× slower and needs the whole card. Split: sweep on Z-Image, re-render finalists on Qwen with the pose held asymmetric.
- **Z-Image low-VRAM configuration:** `CLIPLoader device: cpu` keeps the 7.5 GB text encoder in RAM — 33 s/image at 12.7 GB VRAM (measured). With the encoder on GPU it needs ≈20 GB and thrashed while Ollama held 6 GB.
- Strongest silhouettes for a hollow lantern (compact, thick, nothing spread wide), in order: **k** (R34 swipe — one paw forward, dynamic), **c**, **d**, **q** (bent, lean), **o** (near-profile, bent, jaw closed), **j**, then the tall totems **i**, **s**, **g**.
- The round-1 images otherwise pass every gate: whole bear, empty grey background, no hard shadows, matte clay, minimal fur. Candidate **d** (elbows bent, paws in front of chest) is the most self-supporting silhouette; **b** (thin outstretched arms) is the worst case for a hollow print.
- Qwen at 1024² with four branches ran at **23.6 / 24.5 GB VRAM** — survivable only because compose shares the model loaders across branches.

**Stage 2**
- `ref_d` → rembg → Hunyuan3D 2.1 (octree 256, 30 steps): **66 s**, 271,556 triangles, **not watertight**, winding not consistent. Repair is a real step, as HANDOFF predicted.
- **The "flat back" fear did not materialise.** From a dead-on frontal reference, 2.1 invented a plausible bear back — shoulders, spine, rump — and the raised forelegs read correctly from every side (`outputs/scratch/mesh_round1_d_views.png`). Multi-view is not needed for this pose.

- **Hunyuan3D 2.1 parameter sweep on `ref_d` (all at 160 mm):** octree 256 → 276k tris; 384 → 615–646k; threshold 0.5/0.6/0.7 → ±1 % tris; seeds 2/3 → 8.6–9.3 % support; 50 steps → 618,812 tris, 8.96% support, 135.6 x 66.8 mm. **Every variant is the same bear**: identical silhouette and back, footprint within 0.3 mm, support 8.6–9.3 % in the same three places (underarms, crotch, under the muzzle). At print scale the voxel remesh (0.6 mm) discards everything above octree 256 anyway. **Settings for the twenty: octree 256, 30 steps, threshold 0.6, any seed.** (`o512` deferred to the end of the queue.) **No-cutout control:** with the grey background left in, 2.1 reconstructs it as a flat 160 × 47 mm *wall* and attaches the bear to it as a relief (879k tris, `outputs/stage2_params/d/nobg_o384_s30_views.png`). Background removal is mandatory, not a nicety.
- **Octree resolution verdict (measured on 8 + 1 meshes, all at 160 mm).** The octree-384 pass on the eight three-quarter candidates (c d g i k o q s, `outputs/stage2_mesh/round2z_o384/`) and the deferred `o512` on `ref_d` settle §6's question: **no, 384/512 does not change anything at print scale.** 384 gives 2.1–2.3× the triangles (c 254k → 571k, k 290k → 652k), 512 gives 4.0× (d 276k → 620k → 1.10M); footprints agree to 0.1 mm, support to 0.1 percentage points (c 8.2/8.3 %, k 10.7/10.7 %, d 8.97/8.95/8.94 %), and side-by-side views sheets show the same silhouette, ears, jaw and paws with the same red support patches. The higher octree only smooths the surface slightly, and the 0.6 mm voxel repair discards even that. **The 256 / 30 steps / threshold 0.6 default stands for every reconstruction.** Per-id tables: `outputs/stage2_mesh/round2z_o384/index.md`, `outputs/stage2_params/d/index.md`.

**Stage 3**
- `tools/mesh_repair.py` (voxel remesh, 0.6 mm pitch, ~8 s): 271,556 non-manifold tris with 874 shells and Euler 349 → **5,876-face solid, Euler 2, manifold3d NoError**, watertight and winding-consistent, 160 mm tall, base opened under each foot. Support need fell from 8.7 % to **6.2 %** — the remainder is the crotch, the underarms and under the muzzle, which is a *pose* question, not a repair one (the Stage-3 5 % gate is not yet met on this pose). `pymeshfix` also survives validation on this mesh and is kept as `--method meshfix`; plain `fill_holes` fails, as predicted. Defaults after review: 12,000 faces (6,000 collapses the open jaw to a slit), base cut taken out of the 160 mm.
- **The non-watertightness is real topology, not an export artifact.** One connected body with ~180 boundary loops and ~873 debris shells and a high Euler number — non-manifold edges from marching-cubes extraction with self-intersections. `fill_holes` cannot fix it by construction; the repair is a volumetric remesh (voxelize to a solid, re-extract), watertight by definition (`tools/mesh_repair.py`). Oriented and scaled to 160 mm the bear is **136 × 63 mm** with **8.6 %** of its surface needing support — well inside the Centauri. This is also the concrete evidence for HANDOFF's TRELLIS 2 pick: its DC remesh does this in-graph.
- **GLB is Y-up.** `check_mesh.py` assumed Z-up and reported a 346 × 408 mm footprint at 160 mm tall — the bear was lying on its back in the checker. Its overhang census is meaningless until the mesh is oriented (`--up` flag being added).

**Infrastructure**
- **Ollama was the VRAM squatter.** The `llama-server` processes are Ollama runners (`qwen3:4b-instruct` 5.1 GB + `bge-m3` 0.7 GB, re-queried every few minutes by something on the box), running as SYSTEM under the scheduled task `OllamaProxySupervisor`. `ollama stop <model>` unloads at once (no elevation); keeping it down needs `Stop-ScheduledTask OllamaProxySupervisor` plus an elevated `Stop-Process` (non-elevated kills return Access Denied). Shut down for this session at the user's request; restore with `Start-ScheduledTask OllamaProxySupervisor` or the Ollama app.
- **The 4090 is not ours alone.** Two `llama-server` processes hold ≈6.2 GB dedicated VRAM (they respawn under new PIDs) and the compositor ≈1 GB; ComfyUI effectively has ≈17 GB. Anything near 20 GB (Qwen-Image 2512 fp8) thrashes — ComfyUI's python reached 47 GB of system commit while streaming weights. With a ≈62 GB WSL/Docker VM also committed, the machine sat at 161 of 163 GB commit and the Claude Code process died (Windows itself stayed up). Policy: check `vram_free` before queuing a big model; group jobs by model family; `POST /free {"unload_models":true}` at every family switch.
- **Z-Image can hang in the VAE decode**, not just the sampler: with the 11.7 GB unet and 7.7 GB text encoder both resident (≈23.5 GB used), one branch's decode sat at 100 % GPU for 7+ minutes with no progress (`r` in round 2z). `/interrupt` does not reach a decode either. Fix: `CLIPLoader device: cpu` (encoder in RAM, ≈12.7 GB peak, 33 s/image) for any run that shares the card with anything — make it the default for Z-Image sweeps.
- **`/interrupt` does not stop a weight-streaming job** — the flag is only checked between sampler steps, and a thrashing step can take minutes. Kill the process instead (filter on `main.py` + `8188`, and *exclude the PowerShell doing the filtering* — the first attempt matched itself).
- **Live previews are a server launch flag.** ComfyUI defaults to *no* in-progress previews; the server was relaunched with `--preview-method auto` (same launcher, same args, plus that flag). There is no UI toggle on this build.
- **The server's HTTP loop starves while the GPU works** — `/object_info` took 50 s mid-job. The frontend sits on its splash screen until that returns; CLI status calls need long timeouts (`curl --max-time 90`). Not a fault, just physics of one process.
- **`comfy assets push` crashes on Windows** *after* uploading: it opens the temp lock read-only and calls `os.fsync`, which raises `EBADF`, so `.comfy/assets.lock.json` is never written. The complete lock is left as `.comfy/assets.lock.<pid>.tmp`. Workaround: merge the newest `.tmp` into `assets.lock.json` (`tools/push_assets.py`). Upstream fix: open the tmp `O_RDWR` or fsync the write handle. Worth reporting to comfy-cli.
- Compose accepts a **STRING output → STRING input** wire between fragments (that is how the in-graph prompt builder feeds `t2i_qwen`), and accepts a sink fragment (one with its own `SaveGLB` and no outputs) as the last step without appending a save.
- Loading an API-format graph into the frontend (`app.loadApiJson`) keeps the API node ids, so live progress/previews map onto the loaded nodes — but it carries no positions, so a layout pass is required to make it readable.
- Playwright cannot navigate away from a ComfyUI tab with an unsaved workflow until the `beforeunload` dialog is accepted.

### Round 3z (2026-09-10 01:10–02:16): pose engineering works; the plinth is worth two points

Twenty references (`blueprints/stage1_refs_round3z.yaml`), all twenty reconstructed at 256/30/0.6,
all twenty repaired with `mesh_repair.py --open-base` and scored on the **post-repair** support figure
(the raw figure is inflated by the underside of the rock slab, which the base cut removes: `d` reads
16.5 % raw and 4.4 % repaired). Ranking, support % of surface at 160 mm:

| id | pose | base | style | support |
|---|---|---|---|---|
| l | both arms up, head back roaring at the sky | rock | bronze | **1.76** |
| h | one arm up, one down, roaring at the sky | rock | clay | 1.79 |
| g | one arm up, one down, jaw closed | legs | clay | 1.94 |
| j | totem column, roaring at the sky | rock | clay | 2.42 |
| b | both arms up, roaring at the sky | rock | clay | 2.47 |
| k | both arms up, roaring at the sky | legs | bronze | 3.08 |
| a | both arms up, roaring at the sky | legs | clay | 3.49 |
| t | totem column, chin tucked | rock | bronze | 3.76 |
| s | totem column, jaw closed | legs | bronze | 3.82 |
| r | one arm up, jaw closed | rock | bronze | 3.90 |
| n | boxer's guard, jaw closed | rock | bronze | 3.91 |
| p | paws down (asked for clasp), roaring at the sky | rock | bronze | 3.98 |
| i | totem column, chin tucked | legs | clay | 4.03 |
| e | paws down (asked for clasp), roaring at the sky | legs | clay | 4.07 |
| f | paws clasped, jaw closed | rock | clay | 4.39 |
| d | boxer's guard, jaw closed | rock | clay | 4.42 |
| o | paws clasped, jaw closed | legs | bronze | 4.86 |
| c | boxer's guard, jaw closed | legs | clay | 5.16 |
| q | one arm up, chin tucked | legs | bronze | 5.18 |
| m | boxer's guard, chin tucked | legs | bronze | 5.84 |

Seventeen of twenty are under the 5 % gate; round 2z had none (best 5.2 %). What the matrix says:

- **The rock plinth is worth one to two points in nine of ten matched pairs** (c 5.16 → d 4.42,
  m 5.84 → n 3.91, k 3.08 → l 1.76, a 3.49 → b 2.47, i 4.03 → j 2.42, q 5.18 → r 3.90, o 4.86 → p 3.98,
  g 1.94 → h 1.79, s 3.82 → t 3.76; only e → f went the other way, and those differ in head too). It
  is also the plate contact, and after the base cut its bottom is the single opening for the pole and
  light. Z-Image rendered every "rock" item on a slab and ignored "hind legs pressed together" in every
  "legs" item, so the crotch band (z 27–53 mm) is the residual red on all twenty.
- **Head up beats head down.** Every sky-roar variant beats its closed-jaw or chin-tucked twin; the
  three bears over the gate are all chin-tucked or closed-jaw guards without a rock. Throwing the head
  back removes the muzzle underside entirely.
- **Arms: overhead or one-up-one-down are best; guard and clasp are worst.** Vertical forearms still
  shade the belly and armpits when the elbows sit on the ribs.
- **The bronze prompt reconstructs as a grizzly.** k/l/p/r keep the long muzzle, the shoulder hump and
  the limb masses; the fur texture in the reference does not survive the voxel remesh and 12k-face
  decimation, so it costs nothing. The clay prompt reconstructs as a plush toy every time.
- **Frontal references reconstruct as well as three-quarter ones** (b, l and k are frontal). The
  three-quarter rule from HANDOFF was never tested and is dropped as a filter.
- **Hunyuan kept the asymmetric one-arm-up pose** (g, h, q, r) this round; the symmetrising seen on
  round-2 `k` was not repeated.

Shipped to `print-ready/`: `bear-r3l-bronze-sky-roar-on-rock-160mm.stl` (**recommended**), plus r3h,
r3k, r3b and r3d. Infrastructure findings from the same night (commit-limit deaths, Ollama's supervisor
loop and 20-second warm client) are in the `comfy-local-ops` skill and `docs/OLLAMA_ON_SOUL.md`.

### Round 4z (2026-09-10 12:00–12:24): identity over overhang — the chosen bear

After round 3 the user's verdict was "much more fierce and recognizable as a GRIZZLY bear, distinctive
features" and "don't fill between legs". Round 4 (`blueprints/stage1_refs_round4z.yaml`) put the field
marks into every prompt (shoulder hump, dished face with a broad short muzzle, small round ears, long
straight claws, massive neck, furrowed brow, lips drawn back over the canines), kept the rock and the
printable arm poses, let the face come forward (snarl / roar raised 30° / open jaws) and split the
matrix between the bronze style and a "museum-grade sculpture with fur massed in bold clumps" style.
All twenty reconstructed at 256/30/0.6 and repaired with the quality recipe, **no leg fill**.

Post-repair support: h 2.3 · b 3.0 · f 3.5 · d 3.7 · r 3.7 · a 3.8 (needed `--pitch 0.6`: the shell
leaked at 0.4) · q 4.0 · n 4.1 · k 4.3 · j 4.6 · t 4.7 · m 4.8 · e 4.8 · g 5.0 · s 5.1 · i 5.4 ·
p 5.4 · o 5.6 · l 5.6 · c 5.8. Thirteen of twenty under the gate with the face visible.

- **The user chose `b`** (front, arms overhead, roar raised 30°, bronze): a grizzly with the jaw open
  and canines showing, claws, on the rock, at 3.0 %. Shipped as
  `print-ready/bear-r4b-grizzly-roar-arms-up-on-rock-160mm.stl`.
- **Naming the field marks works.** Every one of the twenty references reads as a grizzly; round 3's
  "bronze with a heavy brow" line had not been enough. Z-Image's faces tend to wide-eyed rather than
  furious; the roar/jaws variants carry the aggression, the "snarl" clause does not add much.
- **The carved-fur (museum) style survives reconstruction as a lumpy muscular hide**, not noise; the
  bronze style stays smoother. Both are usable; the user preferred bronze.
- **Forward-facing heads cost about a point** (muzzle underside) against the sky-roar of round 3, which
  is the price of a visible face. Arms-down and paws-forward poses (e, o) are the most animal-like
  in the round and cost 1–2 points more for their forearm undersides.
- **A leaky Hunyuan shell** (round-4 `a`: flood fill escaped, footprint reported in metres) is fixed by
  a coarser pitch; the signature is documented in the `mesh-print-prep` skill.

### Stage 2 switched to TRELLIS.2 (2026-09-10 13:00–14:00): the detail was never in Hunyuan's output

The user's next verdict on the round-4 bear was "overly smooth". Measured before guessing: the *raw*
Hunyuan3D mesh (301k faces, 0.5 mm edges) bends only 2.6° between neighbouring faces — a genuinely smooth
surface, not a detailed one being sanded down by our repair. The carved fur in the reference never made
it into the reconstruction; octree/steps only add triangles to the same smooth blob.

TRELLIS.2 (`microsoft/TRELLIS.2-4B`, ComfyUI-Trellis2 wrapper) was installed in an **isolated** ComfyUI on
port 8190 because its CUDA wheels need torch 2.10 and the pipeline server runs 2.13 (`docs/TRELLIS2_EVAL.md`,
`docs/MACHINE.md`). Same cutout, same bear:

| mesh | faces | dihedral mean / p90 | after repair, 25k faces | support |
|---|---:|---|---|---:|
| Hunyuan3D 2.1 | 301k | 2.59 / 5.55 | 6.58 / 12.78 | 3.03 % |
| TRELLIS.2 HQ (1536 cascade, quad) | 995k | 5.22 / 13.13 | 11.56 / 23.04 | 3.87 % |
| **TRELLIS.2 DCx** (1024 cascade, dual contouring) | 503k | 5.10 / 12.45 | 8.65 / 17.34 | **3.63 %** |

The close-ups (`outputs/stage2_mesh/round4z_trellis/b_closeup_print_3way.png`) settle it: both TRELLIS
meshes have an open jaw with tongue and teeth, eyes, a brow, fur ridges and separate claws; Hunyuan has no
face. **DCx is the Stage 2 default** — finer, more naturalistic fur, less support, 8 min instead of 12.
Caveats: the dihedral metric is scale-dependent (smaller faces → smaller angles) so it must not be compared
across face counts; and TRELLIS costs 8–12 min per bear against Hunyuan's 66 s, so Hunyuan stays the sweep
tool and TRELLIS the finalist tool.

### Detail at print size (14:30): pitch and face budget, not the model

The first 240 mm totem was a faceted blob although it came from the TRELLIS mesh: built at 0.5 mm pitch with
60k faces over a surface 2.25× the 160's area and ten Taubin passes. Rebuilt with `mesh_repair.py --pitch 0.3
--faces 250000 --smooth 3` (3.4 M marching-cubes faces → 250k, 102 s) the eyes, nose, teeth, fur ridges and
claws are all there (`print-ready/preview-totem-r4b-TRELLIS-240mm-closeup.png`). Rules: detail scales with
pitch and the face budget, smoothing beyond ~3 passes eats fur, and the hollowing step must never resample
the outer surface (`hollow.py --outer keep`). The printer is the remaining ceiling: 0.6 mm nozzle × 0.2 mm
layers cannot render relief under ~0.5 mm, so a 0.4 mm nozzle or thinner layers is the next lever, not the
mesh. A maximum-resolution TRELLIS source (sparse 64–128, 1536 cascade) is the last mesh-side lever and was
being generated at the time of writing.

### Hollowing for the light (Stage 4 prep, `tools/hollow.py`)

The totem is a modelled shell, not a slicer trick: a Euclidean distance transform on the voxelised solid
keeps only material within the wall of the surface, so the wall is uniform (measured 1.95 mm mean, 1.80–2.10
for a nominal 2.0) and the UV light inside charges the phosphor evenly; ears and claws stay solid on their
own. The cavity opens through the plinth (89 × 87 mm at 160, 133 × 129 at 240). Material: 78 cm³ ≈ 97 g at
160 mm, 194 cm³ ≈ 240 g at 240 mm — against 409 / 1353 cm³ solid. Slicing changes: slice it as an ordinary
solid (3 walls, any infill); the cavity ceilings are real overhangs — let tree supports grow up inside
through the base opening or accept sag where nobody looks. Lessons that cost an hour each: a per-body
winding fix turns the cavity into a second solid; trimesh's boolean wrapper re-orients skins (call
manifold3d directly); a global simplify with a tolerance near the wall pushes the skins through each other
(decimate each skin on its own, cavity skin right-side-out); trimesh's subdivision voxeliser wants 13 GB on a
decimated mesh (rasterise with a barycentric lattice instead).

### Keychain (Stage 5, `tools/keychain.py`): the strongest loop is no loop

At 20 % (32 mm) the user first asked for a ring on the head, then judged it likely to snap. Measured at the
thinnest horizontal section: a 2.2 mm ring carries 7.5 mm² across two legs, a 3.0 mm ring 14.0 mm², a slab
bail with a drilled hole 24 mm² — and **sinking the ring deeper does nothing** (the weak line is the ring's
own equator, which stays in air because the hole must stay clear). The bail looked like hardware bolted to
the bear and was rejected. The actual requirement turned out to be a 1 mm stretch cord, so the answer is a
3 mm tunnel bored through the skull only (`--style hole --through head`), exiting into the 2 mm gaps between
the head and the raised arms, at 86 % of the height where 2.4 mm of crown remains above the bore: ~55 mm² of
material around it, nothing protrudes, invisible from the front. First attempt bored the arms (the bore was
centred on the paw tips and ran full width) — the fix finds the skull as its own slice island.

## 4. Division of labour (this session)

| Agent | Owns | Delivers |
|---|---|---|
| `sweep` | `prompt_builder`, `t2i_qwen`, `stage1_refs.yaml`, `comfy.yaml`, `tools/sheet.py` | the 20-candidate Stage-1 round, contact sheet |
| `stage2` | `stage2_*.yaml`, `tools/push_assets.py`, `tools/collect.py`, `assets/round2/` | param sweep on `d`, reconstruction of all 20, output mirroring |
| `meshtools` | `check_mesh.py --up`, `tools/mesh_views.py`, `mesh_repair.py`, `mesh_batch.py` | six-view renders, watertight repair + decimate + open base, batch reports |
| `tooling` | `tap_*`, `tools/build.py`, `tools/ui/`, `PIPELINE.md`, `.gitignore`, **git** | compiler pass, grouped/coloured browser view, docs, commits |
| main session | the browser, the queue, this file | shows results in chat as they land, steers, keeps the GPU fed |

Only `tooling` commits routinely; the main session commits its own docs. Later agents: `sweep2` (Z-Image round), `stage2b` (reconstructions + 384 pass), `meshtools2` (voxel remesh), `site` (docs/index.html). All finished or finishing by 01:00.

## 5. Output tree

```
D:\sync\Comfy\3d-bear\<stage>\<round>\<id>[_<variant>]_00001_.png|.glb   ← server, synced
D:\sync\Comfy\debug\3d-bear\<stage>\<round>\<id>_<what>_00001_.png         ← taps (only with --debug)

outputs/
  stage1_refs/round1/  ref_a..d.png               (the frontal round)
  stage1_refs/round2/  a..t.png, items.json, sheet.png, index.md
  stage2_params/d/     o256_s30.glb … nobg.glb, mesh_report.md, *_views.png
  stage2_mesh/round2/  a..t.glb, a..t_cutout.png, mesh_report.md, index.md
  stage3_print/        <id>_print.stl, reports
  <stage>/<round>/picks/   chosen candidates + finals (committed)
  scratch/             throwaway runs (mesh_round1_d.glb = first ever mesh)
```

## 6. Open questions

- Does the round-2 view language actually produce three-quarter views? (sheet pending)
- ~~Does octree 384/512 buy printable detail, or just triangles?~~ Answered in §3: just triangles (2–4×), nothing visible at 160 mm; 256 stands.
- Does leaving the grey background in hurt reconstruction? (no-rembg control pending)
- Is `fill_holes` enough to make 2.1 output watertight, or is a manifold rebuild needed? (`mesh_repair.py` pending)
- Multi-view Hunyuan3D (`hunyuan3d-dit-v2-mv`) is not on disk; only fetch it if the backs are bad.

## 7. State at handoff (2026-09-10, ~15:00)

**Done.** Four reference rounds, 66 Hunyuan reconstructions, TRELLIS.2 installed in an isolated
environment and adopted for finalists, the repair chain with its measured recipe, a hollowing stage, a
keychain stage, and the user's chosen bear (round-4 `b`) delivered in every form:

| file (in `print-ready/`) | what |
|---|---|
| `totem-bear-r4b-TRELLIS-240mm-hollow-2.5mm.stl` | **the Goldrush totem**, 240 mm, high-detail, 2.5 mm wall, ~240 g |
| `totem-bear-r4b-TRELLIS-160mm-hollow-2mm.stl` | the same at 160 mm, 2 mm wall, ~97 g |
| `keychain-bear-r4b-TRELLIS-32mm-corded.stl` | 32 mm, 3 mm cord tunnel through the skull |
| `bear-r4b-TRELLIS-grizzly-roar-on-rock-160mm.stl` | the validated solid everything above was cut from |

**Next steps, in order.**
1. Print the totem (settings in `print-ready/README.md`; slice as a solid; decide on internal supports).
2. If the maximum-resolution TRELLIS source lands and is visibly better, rebuild the 240 from it:
   `mesh_repair.py --height 240 --pitch 0.3 --faces 250000 --smooth 3` then `hollow.py --wall 2.5 --outer keep`.
3. Nozzle/layer choice is now the detail ceiling (0.4 mm nozzle or 0.12 mm layers), a hardware call.
4. Showcase (`docs/index.html`) still stops at round 2; rounds 3–4, TRELLIS and the totem deserve a spread.
   It is published privately as an artifact; GitHub Pages needs one toggle by the owner (`main` / `/docs`).
5. Machine hygiene before any long GPU job: `docs/MACHINE.md` (Ollama supervisor loop, commit limit).
