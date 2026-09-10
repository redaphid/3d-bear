---
name: bear-pipeline
description: Runbook for the 3d-bear project — generate reference sweeps, reconstruct with Hunyuan3D, repair to print-ready STLs, and where everything lands. Load for ANY work in D:\Projects\3d-bear (new rounds, picks, prints, docs) before touching fragments, blueprints, tools or outputs.
---

# bear-pipeline — how this project is run

Read first: `APPROACH.md` (method + measured findings), `PIPELINE.md` (reference),
`HANDOFF.md` (what/why). This skill is the short operational version.

## The four stages and their tools

| Stage | Command | Output |
|---|---|---|
| 1 references | `python tools/build.py blueprints/stage1_refs_z.yaml` → `comfy --json run --workflow blueprints/stage1_refs_z.compiled.00N.json` (one per chunk) | `D:\sync\Comfy\3d-bear\stage1_refs\<round>\ref\<id>_00001_.png` |
| 1 sheet | `python tools/sheet.py outputs/stage1_refs/<round> --items …/items.json --cols 5 --out …/sheet.png` | contact sheet, pick by id |
| 2 reconstruct | copy refs to `assets/<round>/<id>.png` → `python tools/push_assets.py` → `python tools/build.py blueprints/stage2_round2z.yaml --debug` → run each chunk | `…\3d-bear\stage2_mesh\<round>\<id>_00001_.glb` + cutout taps under `…\debug\…` |
| 3 print | `python tools/mesh_repair.py outputs/stage2_mesh/<round>/<id>.glb --out outputs/stage3_print/<round>/<id>_print.stl --height 160 --open-base --views` | validated STL + six-view sheet |
| ship | copy to `print-ready/bear-<id>-<pose>-160mm.stl` + `preview-bear-<id>.png`, update `print-ready/README.md` | what the slicer gets |

Mirror server outputs into the project with `python tools/collect.py` (byte-for-byte —
the PNG/GLB metadata is the re-runnable workflow) or the per-file watcher pattern below.

## Rules that were paid for

- **Edit source, never the compiled JSON.** Fragments (`fragments/*.json`) and
  blueprints (`blueprints/*.yaml`) are source; `tools/build.py` is the compiler.
- **Prompts are built in-graph** (`prompt_builder` → `t2i_*` STRING input). Vary
  `view / pose / mass / mouth` per `foreach` item; shared text lives in `comfy.yaml vars:`.
- **View clauses must be geometric** ("body rotated ~45°, near shoulder toward the
  camera") and early in the prompt. **Raised-arms poses snap to frontal** on
  Z-Image; bent / tall / swipe poses turn as asked. Frontal references reconstruct
  just as well (round 3z: b, k, l) — the view is not a filter.
- **Round 3z settled the pose (17/20 under the 5 % gate, round 2z had 0/20):** put the
  bear **on a rock plinth** (worth 1–2 points in 9 of 10 matched pairs, and it is the
  plate contact + the base opening), **head thrown back roaring at the sky** (no muzzle
  underside), arms **overhead or one-up-one-down** (guard/clasp shade the belly), and
  use the **bronze prompt** (grizzly anatomy survives the remesh; fur texture does not
  cost anything; the clay prompt gives a plush toy). Z-Image ignores "legs together".
- **Score on the post-repair figure** (`mesh_repair.py --open-base` then `check_mesh.py`
  on the STL): the raw census counts the slab's underside (d: 16.5 % raw, 4.4 % repaired).
- **Z-Image Turbo with `load_clip_device: cpu`** is the sweep generator on this box
  (33 s/image, 12.7 GB). With the encoder on GPU it hangs in VAE decode. Qwen-Image
  2512 follows view clauses better but needs the whole card — use it only for
  finalists with Ollama down.
- **Hunyuan3D 2.1 settings are settled: octree 256, 30 steps, threshold 0.6.**
  Higher octree/steps/threshold/seed all produce the same bear at print scale.
- **rembg is mandatory** — without it the grey backdrop becomes a 160 mm wall.
- **Never hole-fill; voxel-remesh.** Hunyuan output is non-manifold marching-cubes
  soup; `mesh_repair.py` (largest shell → voxelise 0.6 mm → re-extract → validate
  with manifold3d → 12k faces → open base) is the only path that yields a solid.
- **`--height` is the printed height**, base cut included.
- **Model families never interleave on the GPU** (Z-Image ≈12 GB resident vs
  Hunyuan ≈4 GB): finish one family, `POST /free {"unload_models":true}`, then the next.
- **Debug taps** = SaveImage/SaveGLB whose `filename_prefix` starts `debug/`;
  `build.py` strips them unless `--debug`. Cutout taps stay ON for reconstruction rounds.
- `comfy assets push` crashes on Windows after uploading — always use
  `tools/push_assets.py` (merges the leftover `.comfy/assets.lock.<pid>.tmp`).
- **Submit with `python tools/submit.py <compiled.json…> --ids .comfy/<round>_ids.txt`**,
  not `comfy run`: every `comfy --json run` left a python.exe behind (~90 in one
  night). submit.py POSTs `/prompt` and strips build.py's `_meta` key, which ComfyUI
  otherwise rejects as a node without class_type.
- **The memory guard must log the number it computes** (`.comfy/guard.log`) and kill
  only the process whose command line has `main.py` *and* `--port 8188`. Two silent
  server deaths on 2026-09-10 (commit 114–116 GB, no traceback, ~2 min after a job
  started) coincided with an agent-written guard; keep exactly one guard running.

## Watching arrivals (the user wants to see each item as it exists)

```bash
# one line per new file; render meshes six ways as they land
D="D:/sync/Comfy/3d-bear/stage2_mesh/<round>"; SEEN=""
for i in $(seq 1 360); do for f in $(ls "$D" | grep '\.glb$'); do case " $SEEN " in *" $f "*) ;; *)
  SEEN="$SEEN $f"; stem=${f%_00001_.glb}; cp "$D/$f" outputs/stage2_mesh/<round>/$stem.glb
  python tools/mesh_views.py outputs/stage2_mesh/<round>/$stem.glb --out outputs/stage2_mesh/<round>/${stem}_views.png --height 160
  echo "VIEWS $stem";; esac; done; sleep 10; done
```
Run it as a Monitor; `Read` each `_views.png` into chat. Rank with
`check_mesh.py <glb> --height 160` (`needs support %` is the print gate: < 5 %).

## Adding a round

1. New blueprint (copy `stage1_refs_z.yaml`), new `<round>` name in `output_prefix`
   and item prefixes. Keep ids a–t so sheets/indexes line up.
2. Build, run chunks, sheet, pick, reconstruct picks (or all 20 — GPU is cheap),
   repair, ship to `print-ready/`.
3. Record what was learned in `APPROACH.md §3`; commit outputs that are samples
   (PNGs, sheets, STLs, indexes; raw GLBs only by `git add -f` for picks).

## Operating the ComfyUI box

See the user-level `comfy-local-ops` skill: launch line (needs
`--preview-method auto`), kill/relaunch, VRAM/commit checks, the memory guard,
Ollama shutdown, and loading the running graph onto the browser canvas.
