# 3d-bear

A rearing grizzly bear — generated in ComfyUI, reconstructed to 3D, repaired into a
watertight solid, and printed hollow in glow-in-the-dark filament to be lit from
inside on a pole. A totem for Goldrush 2026.

**Want a bear right now?** `print-ready/` has validated STLs with previews and slicer
settings. `bear-r4b-grizzly-roar-arms-up-on-rock-160mm.stl` is the one the user chose (3.0 % support).

**Want the story?** `docs/index.html` is the showcase (GitHub Pages).

## The pipeline

```
reference images  →  image-to-3D            →  printable mesh  →  hollow shell  →  glowing bear
 Z-Image / Qwen      Hunyuan3D 2.1 (sweeps)    voxel remesh       2–2.5 mm wall     Centauri Carbon 2
 20 per sweep        TRELLIS.2 (finalists)     0.3 mm pitch       base open         solid slice, light inside
```

Everything is source-controlled as *programs*: fragments are functions
(`fragments/`), blueprints are programs (`blueprints/`), `tools/build.py` is the
compiler, and every output PNG/GLB carries the workflow that made it.

| Read this | for |
|---|---|
| [`HANDOFF.md`](HANDOFF.md) | what we're making and why; the four stages and their gates; print settings |
| [`APPROACH.md`](APPROACH.md) | how we actually work, every decision with its reason, everything we measured, and the state at handoff |
| [`PIPELINE.md`](PIPELINE.md) | the reference manual: fragments, blueprints, taps, the build, where outputs land |
| [`tools/README.md`](tools/README.md), [`tools/MESH.md`](tools/MESH.md) | the tools, and the mesh-repair rationale |
| [`print-ready/README.md`](print-ready/README.md) | which STL to print and how |
| [`docs/TRELLIS2_EVAL.md`](docs/TRELLIS2_EVAL.md) | why Stage 2 moved to TRELLIS.2 for finalists, and how its isolated environment was built |
| [`docs/MACHINE.md`](docs/MACHINE.md) | the box: three ComfyUI installs, the commit limit, the Ollama supervisor loop, tool quirks |
| [`docs/OLLAMA_ON_SOUL.md`](docs/OLLAMA_ON_SOUL.md) | the Ollama investigation in full, with stop and restore commands |
| [`docs/SPOREFALL_SPRITES.md`](docs/SPOREFALL_SPRITES.md) | a proposal for reusing the pipeline for animated sprite sheets |

## Layout

```
fragments/     typed, reusable graph pieces (t2i_zimage, t2i_qwen, prompt_builder, rembg, hy3d_i2m, tap_*)
blueprints/    one YAML per stage/round; *.compiled.json are build artifacts (ignored)
comfy.yaml     project marker + shared prompt constants (vars:)
assets/        reference images pushed to the ComfyUI input dir ($asset.<round>/<id>.png)
tools/         build.py · submit.py · relaunch.ps1 · push_assets.py · collect.py · sheet.py · ui/ · mesh_*.py · hollow.py · keychain.py
outputs/       <stage>/<round>/… — mirrored from the server, committed as samples
print-ready/   the deliverables
docs/          the showcase page (+ proposals)
templates/     vendored ComfyUI gallery templates the fragments were decomposed from
.claude/skills/bear-pipeline   the operational runbook Claude loads for this repo
```

## Quick start (on the box with the local ComfyUI)

```bash
python tools/build.py blueprints/stage1_refs_z.yaml            # compile a 20-candidate sweep (4 chunks)
comfy --json run --workflow blueprints/stage1_refs_z.compiled.000.json   # … one per chunk
python tools/sheet.py outputs/stage1_refs/<round> --items …/items.json --cols 5 --out …/sheet.png
python tools/push_assets.py                                      # after copying picks into assets/<round>/
python tools/build.py blueprints/stage2_round2z.yaml --debug     # reconstruct (cutout taps on)
python tools/mesh_repair.py outputs/stage2_mesh/<round>/<id>.glb --out out.stl --height 240 --open-base --pitch 0.3 --iso 0.7 --faces 250000 --smooth 3 --views
python tools/hollow.py out.stl --out totem.stl --wall 2.5 --pitch 0.5 --height 240 --outer keep --views      # the shell for the light
python tools/keychain.py out.stl --out keychain.stl --scale 0.2 --style hole --through head --hole 3.0        # 32 mm, cord tunnel
```

Requires the `comfy` CLI, a local ComfyUI with Hunyuan3D 2.1 and Z-Image Turbo
weights, and Python with `trimesh manifold3d pillow matplotlib`.

## License

MIT — see [LICENSE.md](LICENSE.md). Every model here was generated in this repo;
nothing is redistributed from anyone else's license.
