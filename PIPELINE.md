# PIPELINE — how the bear gets built

Four stages, each a gate. Stages 1 and 2 run in ComfyUI from this repo; 3 and 4
are mesh tools and the printer (see HANDOFF.md for the why and the settings).

```
 stage 1                stage 2                 stage 3               stage 4
 reference images  -->  image-to-3D        -->  printable mesh   -->  glowing print
 t2i_qwen sweep         rembg + Hunyuan3D 2.1   check_mesh.py,        slice, print,
 -> contact sheet       -> .glb per pick        repair, decimate,     charge, dark room
 -> pick ids            (TRELLIS 2 absent)      scale, open base
```

## Fragments are functions

A fragment (`fragments/<name>.json`) is a few ComfyUI nodes with a typed
interface: inputs are wires, params are widget values, outputs are wires.
`comfy --json workflow fragment show <name>` prints the full interface.

| fragment | inputs | outputs | key params |
|---|---|---|---|
| `prompt_builder` | — | `prompt: STRING` | `subject, view, pose, mass, mouth, style` (joined with spaces) |
| `t2i_qwen` | `prompt: STRING` | `image: IMAGE` | `ksampler_seed`, `int_steps_value`, `float_cfg_value`, `emptysd3latentimage_width/height`, `clip_text_encode_negative_prompt_text`, `load_lora_lora_name` |
| `rembg` | `image: IMAGE` | `image: IMAGE` | — |
| `tap_image` | `image: IMAGE` | — (terminal) | `label` = `debug/<what>` |
| `tap_mesh` | `mesh: MESH` | — (terminal) | `label` = `debug/<what>` |
| `hy3d_i2m` | `clip_vision_encode_image: IMAGE` | — (saves the GLB itself) | `save_3d_model_filename_prefix`, `vaedecodehunyuan3d_octree_resolution`, `ksampler_seed`, `ksampler_steps`, `voxel_to_mesh_threshold` |

Templates the fragments were decomposed from live in `templates/` (vendored
gallery workflows; never edit them, decompose them).

## Blueprints are programs

A blueprint (`blueprints/<name>.yaml`) calls fragments in order and wires them
with `$alias.output`. `foreach:` runs the whole pipeline once per item inside
ONE graph, so ComfyUI parallelises the branches. `$item.field` reads the item,
`$var.name` reads `vars:` in `comfy.yaml`, `$asset.path` reads a pushed file
under `assets/`.

```yaml
foreach:
  - {id: c, ref: $asset.refs/c.png, prefix: outputs/round2/mesh/c, octree: 256, seed: 1}
pipeline:
  - fragment: rembg
    alias: cut
    inputs: {image: $item.ref}
  - fragment: tap_image                 # debug probe, stripped unless --debug
    alias: tap_cut
    inputs: {image: $cut.image}
    params: {label: debug/cutout}
  - fragment: hy3d_i2m
    alias: mesh
    inputs: {clip_vision_encode_image: $cut.image}
    params: {save_3d_model_filename_prefix: $item.prefix, ksampler_seed: $item.seed}
```

- `blueprints/stage1_refs.yaml` — 20-candidate reference sweep, `chunk: 5`.
- `blueprints/stage2_mesh.yaml` — one mesh per picked reference.

## Build, then run

```
python tools/build.py blueprints/stage2_mesh.yaml            # deliverable graph
python tools/build.py blueprints/stage2_mesh.yaml --debug    # keeps the taps
comfy --json run --workflow blueprints/stage2_mesh.compiled.json
comfy --json jobs watch <prompt_id> && comfy --json download <prompt_id>
```

`build.py` is the compiler: it runs `comfy workflow compose`, strips or keeps
taps, stamps `_meta.debug` / `_meta.built_at`, and runs `comfy validate`. The
`*.compiled.json` files are build artifacts (git-ignored). Never edit them;
change the blueprint or fragment and rebuild.

### Taps: debuggable inputs and outputs

A tap is any `SaveImage` / `SaveGLB` whose `filename_prefix` starts with
`debug/`. Wire one after any intermediate you might want to look at. They cost
nothing by default:

- `build.py` removes them unless you pass `--debug`.
- The browser view shows them greyed and **bypassed** (purple tint).

To look at one intermediate without rebuilding: open the workflow in the
browser view, click the tap, press `Ctrl+B` to un-bypass it, and Run. Only the
tap executes — every upstream node is a cache hit. To add a tap to a
blueprint, insert a `tap_image` / `tap_mesh` step wired to the output you
want (example above) and rebuild.

Tap files land in ComfyUI's output dir under `debug/` (for example
`debug/cutout_00001_.png`).

## The loop: sweep, sheet, pick, next stage

1. **Sweep** — one blueprint, many `foreach` items, one job per chunk.
2. **Sheet** — `python tools/sheet.py outputs/round2 --items outputs/round2/items.json --cols 5 --out outputs/round2/sheet.png`
   tiles every candidate with `id / tag / seed`. Sheets and `items.json` are
   the only outputs committed to git.
3. **Pick** — choose by id from the sheet.
4. **Promote** — `cp outputs/round2/<id>.png assets/refs/<id>.png && comfy --json assets push`
   (on Windows the CLI currently crashes after the upload; rename the newest
   `.comfy/assets.lock.*.tmp` to `.comfy/assets.lock.json`).
5. **Next stage** — add `{id, ref: $asset.refs/<id>.png, ...}` to the next
   blueprint's `foreach`, build, run.

## Where outputs land

| what | prefix in the blueprint | on disk |
|---|---|---|
| Stage 1 images | `output_prefix: outputs/round2/ref` | ComfyUI output dir: `outputs/round2/ref/<id>_00001_.png`; `comfy download` copies them into `outputs/` as `<id>_000.png`; the sweep renames to `outputs/round2/<id>.png` |
| Stage 2 meshes | `prefix: outputs/round2/mesh/<id>` | ComfyUI output dir: `outputs/round2/mesh/<id>_00001_.glb` |
| taps | `label: debug/<what>` | ComfyUI output dir: `debug/<what>_00001_.png` |

The ComfyUI output dir on `soul` is `D:\sync\Comfy`. `outputs/` in this repo is
git-ignored except `sheet*.png` and `items.json`.

## The browser view

```
python tools/ui/publish.py blueprints/stage2_mesh.compiled.json --name stage2 --labels outputs/round2/items.json
```

uploads the compiled graph and `tools/ui/layout.js` to ComfyUI userdata and
prints a JS snippet. Paste it into the browser console (F12) on
http://127.0.0.1:8188 and the graph is imported, laid out, and saved as the
workflow `bear/stage2` in the Workflows sidebar. Each `foreach` item becomes
its own horizontal band (a group titled `<id>  ·  <tag>`), nodes run left to
right by data flow, and every node is coloured by its role:

| role | colour | nodes |
|---|---|---|
| loader | blue | CLIPLoader, VAELoader, UNETLoader, ImageOnlyCheckpointLoader, LoRA |
| input | teal-blue | LoadImage (an `$asset`) |
| prompt | green | StringConcatenate, CLIPTextEncode and the primitives feeding them |
| sample | orange | KSampler, Empty*Latent*, ModelSampling*, steps/cfg switches |
| decode | teal | VAEDecode |
| cutout | yellow | rembg |
| recon | magenta | CLIPVisionEncode, Hunyuan3D*, VoxelToMesh |
| tap | grey (purple tint = bypassed) | SaveImage/SaveGLB with a `debug/` prefix |
| output | red | the deliverable SaveImage / SaveGLB |

A Legend group with one swatch per role sits under the last band. Publish a
`--debug` build if you want the taps present in the view.

## How to add a candidate

**Stage 1:** add an item to `foreach` in `blueprints/stage1_refs.yaml`
(`id`, `seed`, `view`, `pose`, `mass`, `mouth`, `tag`) and the same entry to
`outputs/round2/items.json`; `python tools/build.py blueprints/stage1_refs.yaml`
and run the chunk it landed in.

**Stage 2:** promote the picked PNG into `assets/refs/<id>.png`, push, add the
item to `blueprints/stage2_mesh.yaml`, build, run. Vary `octree` (256 → 384 →
512) and `seed` as separate items if the first mesh is close but not right.

## How to add a stage

1. Find a working graph: `comfy --json templates ls --type 3d` then
   `comfy templates fetch <name> --out templates/ref_<x>.json`, or a node via
   `comfy --json nodes show <Class>`.
2. Turn it into a fragment: `comfy workflow decompose templates/ref_<x>.json --name <x>`
   (or hand-author a 1–15 node fragment) and
   `comfy --json workflow fragment validate <x>`.
3. Write `blueprints/stage<N>_<x>.yaml` with a `foreach` over the picks from
   the previous stage; wire `$alias.output` between steps; add taps after
   anything you will want to inspect.
4. `python tools/build.py blueprints/stage<N>_<x>.yaml`, publish it to the
   browser view, run it.

## Stage 3 and shipping (added after the first night)

- `tools/collect.py <server_subdir> <project_dir>` mirrors server outputs byte-for-byte and writes an `index.md`
  (seed/steps/octree read from each file's own branch of the embedded prompt).
- `tools/push_assets.py` wraps `comfy assets push` (which crashes on Windows after uploading) and merges the
  leftover `.comfy/assets.lock.<pid>.tmp` into the lock.
- `python tools/mesh_repair.py <glb> --out <stl> --height 160 --open-base --pitch 0.4 --iso 0.7 --faces 25000 --smooth --views` (the measured recipe; never `--fill-legs` — the block between the legs was rejected as a wall, `outputs/stage3_print/quality/report.md`) — largest shell → voxel remesh
  → manifold validation → 12k faces → base cut. Hole-filling cannot repair Hunyuan output (non-manifold
  marching-cubes edges); the voxel remesh is watertight by construction. `--height` is the printed height.
- `tools/mesh_views.py` (six views, red = needs support), `tools/mesh_batch.py` / `mesh_index.py` (per-directory
  reports). Rationale and defaults: `tools/MESH.md`.
- Ship to `print-ready/bear-<id>-<pose>-160mm.stl` with `preview-bear-<id>.png` and a row in `print-ready/README.md`.

## Operating notes (this box)

- Z-Image sweeps: `load_clip_device: cpu` (default in `stage1_refs_z.yaml`) — with the encoder on the GPU a
  branch can hang in VAE decode. Qwen-Image 2512 only with Ollama shut down.
- Model families never share the card: finish Z-Image chunks, `POST /free {"unload_models":true}`, then Hunyuan.
- Hunyuan3D settings are settled at octree 256 / 30 steps / threshold 0.6 (the sweep showed no difference at print
  scale). rembg is mandatory (the control reconstructed the backdrop as a wall).
- The full machine runbook (launch line with `--preview-method auto`, safe kill, memory guard, Ollama) is the
  user-level Claude skill `comfy-local-ops`; the project runbook is `.claude/skills/bear-pipeline`.
