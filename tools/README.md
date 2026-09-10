# tools/

Small scripts that sit around the `comfy` CLI. Each one is a single file with
a docstring at the top; `python tools/<name>.py --help` prints usage.

**`build.py`** — the compiler driver. `python tools/build.py blueprints/<x>.yaml
[--debug] [--no-validate]` runs `comfy workflow compose`, then rewrites the
compiled artifact in place: debug taps (any SaveImage/SaveGLB whose
`filename_prefix` starts with `debug/`) are stripped unless `--debug`, their
ids pruned from `_meta.items`, and `_meta.debug` / `_meta.built_at` /
`_meta.taps` are stamped. Finally it runs `comfy validate` and prints one line
per file (node count, taps kept/stripped, valid). Non-zero exit with the CLI's
hint on any failure. It is a compiler pass, not a hand-edit: never edit a
`*.compiled.json`, change the blueprint and rebuild.

**`ui/layout.js`** — browser-side layout for the ComfyUI frontend. Exposes
`layoutBearGraph(app, meta, {labels})`. Given a graph imported with
`app.loadApiJson`, it classifies every node by role (loader, input, prompt,
sample, decode, cutout, recon, tap, output), lays the graph out as one
horizontal band per `_meta.items` entry (data flow left to right, shared nodes
in a left column), colours nodes by role with a legend, sets debug taps to
bypass (`mode = 4`), and fits the canvas. No bundler; it is fetched from
ComfyUI userdata at runtime.

**`ui/publish.py`** — `python tools/ui/publish.py <compiled.json> --name <n>
[--labels items.json]` uploads the compiled JSON and `layout.js` to ComfyUI
userdata (`bear/<n>.api.json`, `bear/layout.js`) and prints a JS bootstrap.
Run that bootstrap in the browser console (or via automation) and the graph is
imported, laid out, and saved as the workflow `bear/<n>` so it appears in the
Workflows sidebar with groups, colours and bypassed taps. `--labels` appends a
tag to each band's title (accepts the contact-sheet `items.json`).

**`sheet.py`** — contact sheet for a sweep: `python tools/sheet.py
outputs/round2 --items outputs/round2/items.json --cols 5 --out
outputs/round2/sheet.png` tiles the item PNGs with an `id / tag / seed` label
strip so a candidate can be picked by id. Also writes a half-size
`sheet_small.png`.

**`../check_mesh.py`** — Stage 3 printability report for a mesh (watertight,
winding, volume, footprint, height, overhang census). Lives at the repo root.
