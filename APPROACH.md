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
- **The non-watertightness is real topology, not an export artifact.** One connected body with ~180 boundary loops and ~873 debris shells and a high Euler number — non-manifold edges from marching-cubes extraction with self-intersections. `fill_holes` cannot fix it by construction; the repair is a volumetric remesh (voxelize to a solid, re-extract), watertight by definition (`tools/mesh_repair.py`). Oriented and scaled to 160 mm the bear is **136 × 63 mm** with **8.6 %** of its surface needing support — well inside the Centauri. This is also the concrete evidence for HANDOFF's TRELLIS 2 pick: its DC remesh does this in-graph.
- **GLB is Y-up.** `check_mesh.py` assumed Z-up and reported a 346 × 408 mm footprint at 160 mm tall — the bear was lying on its back in the checker. Its overhang census is meaningless until the mesh is oriented (`--up` flag being added).

**Infrastructure**
- **Ollama was the VRAM squatter.** The `llama-server` processes are Ollama runners (`qwen3:4b-instruct` 5.1 GB + `bge-m3` 0.7 GB, re-queried every few minutes by something on the box), running as SYSTEM under the scheduled task `OllamaProxySupervisor`. `ollama stop <model>` unloads at once (no elevation); keeping it down needs `Stop-ScheduledTask OllamaProxySupervisor` plus an elevated `Stop-Process` (non-elevated kills return Access Denied). Shut down for this session at the user's request; restore with `Start-ScheduledTask OllamaProxySupervisor` or the Ollama app.
- **The 4090 is not ours alone.** Two `llama-server` processes hold ≈6.2 GB dedicated VRAM (they respawn under new PIDs) and the compositor ≈1 GB; ComfyUI effectively has ≈17 GB. Anything near 20 GB (Qwen-Image 2512 fp8) thrashes — ComfyUI's python reached 47 GB of system commit while streaming weights. With a ≈62 GB WSL/Docker VM also committed, the machine sat at 161 of 163 GB commit and the Claude Code process died (Windows itself stayed up). Policy: check `vram_free` before queuing a big model; group jobs by model family; `POST /free {"unload_models":true}` at every family switch.
- **`/interrupt` does not stop a weight-streaming job** — the flag is only checked between sampler steps, and a thrashing step can take minutes. Kill the process instead (filter on `main.py` + `8188`, and *exclude the PowerShell doing the filtering* — the first attempt matched itself).
- **Live previews are a server launch flag.** ComfyUI defaults to *no* in-progress previews; the server was relaunched with `--preview-method auto` (same launcher, same args, plus that flag). There is no UI toggle on this build.
- **The server's HTTP loop starves while the GPU works** — `/object_info` took 50 s mid-job. The frontend sits on its splash screen until that returns; CLI status calls need long timeouts (`curl --max-time 90`). Not a fault, just physics of one process.
- **`comfy assets push` crashes on Windows** *after* uploading: it opens the temp lock read-only and calls `os.fsync`, which raises `EBADF`, so `.comfy/assets.lock.json` is never written. The complete lock is left as `.comfy/assets.lock.<pid>.tmp`. Workaround: merge the newest `.tmp` into `assets.lock.json` (`tools/push_assets.py`). Upstream fix: open the tmp `O_RDWR` or fsync the write handle. Worth reporting to comfy-cli.
- Compose accepts a **STRING output → STRING input** wire between fragments (that is how the in-graph prompt builder feeds `t2i_qwen`), and accepts a sink fragment (one with its own `SaveGLB` and no outputs) as the last step without appending a save.
- Loading an API-format graph into the frontend (`app.loadApiJson`) keeps the API node ids, so live progress/previews map onto the loaded nodes — but it carries no positions, so a layout pass is required to make it readable.
- Playwright cannot navigate away from a ComfyUI tab with an unsaved workflow until the `beforeunload` dialog is accepted.

## 4. Division of labour (this session)

| Agent | Owns | Delivers |
|---|---|---|
| `sweep` | `prompt_builder`, `t2i_qwen`, `stage1_refs.yaml`, `comfy.yaml`, `tools/sheet.py` | the 20-candidate Stage-1 round, contact sheet |
| `stage2` | `stage2_*.yaml`, `tools/push_assets.py`, `tools/collect.py`, `assets/round2/` | param sweep on `d`, reconstruction of all 20, output mirroring |
| `meshtools` | `check_mesh.py --up`, `tools/mesh_views.py`, `mesh_repair.py`, `mesh_batch.py` | six-view renders, watertight repair + decimate + open base, batch reports |
| `tooling` | `tap_*`, `tools/build.py`, `tools/ui/`, `PIPELINE.md`, `.gitignore`, **git** | compiler pass, grouped/coloured browser view, docs, commits |
| main session | the browser, the queue, this file | shows results in chat as they land, steers, keeps the GPU fed |

Only `tooling` commits routinely; the main session commits its own docs.

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
- Does octree 384/512 buy printable detail, or just triangles? (param sweep pending)
- Does leaving the grey background in hurt reconstruction? (no-rembg control pending)
- Is `fill_holes` enough to make 2.1 output watertight, or is a manifold rebuild needed? (`mesh_repair.py` pending)
- Multi-view Hunyuan3D (`hunyuan3d-dit-v2-mv`) is not on disk; only fetch it if the backs are bad.
