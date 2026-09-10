#!/usr/bin/env python
"""Publish a compiled workflow to the ComfyUI browser view.

    python tools/ui/publish.py blueprints/stage2_mesh.compiled.json --name stage2 \
        [--labels outputs/round2/items.json] [--host http://127.0.0.1:8188] [--print-only]

Uploads the compiled API JSON to ComfyUI userdata as `bear/<name>.api.json` and
tools/ui/layout.js as `bear/layout.js` (POST /api/userdata/<encoded path>?overwrite=true),
then prints a JS bootstrap to paste into the browser console (or run via a
browser automation `evaluate`). The bootstrap imports the API graph with
`app.loadApiJson`, applies `layoutBearGraph` (groups, colours, bypassed taps),
and saves the result as the workflow `bear/<name>` so it shows up in the
Workflows sidebar with its layout intact.

--labels takes a JSON object keyed by item id; values may be strings or objects
with a `tag` field (the contact-sheet items.json). They are appended to each
band's group title.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def post_userdata(host: str, rel_path: str, body: bytes, content_type: str) -> int:
    # The route is /userdata/{file} (one path segment), so slashes are %2F-encoded.
    url = f"{host.rstrip('/')}/api/userdata/{urllib.parse.quote(rel_path, safe='')}?overwrite=true"
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": content_type})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def load_labels(path: Path | None) -> dict:
    if not path:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for k, v in raw.items():
        out[k] = v.get("tag", "") if isinstance(v, dict) else str(v)
    return {k: v for k, v in out.items() if v}


BOOTSTRAP = """(async () => {{
  const ud = (p) => '/api/userdata/' + encodeURIComponent(p);
  const wf = await (await fetch(ud('bear/{name}.api.json') + '?t=' + Date.now())).json();
  const src = await (await fetch(ud('bear/layout.js') + '?t=' + Date.now())).text();
  new Function(src)();                       // defines window.layoutBearGraph
  const meta = wf._meta || {{}};
  const api = Object.fromEntries(Object.entries(wf).filter(([k]) => k !== '_meta'));
  await app.loadApiJson(api, 'bear/{name}');
  const report = layoutBearGraph(app, meta, {{ name: 'bear/{name}', labels: {labels} }});
  await new Promise((res) => setTimeout(res, 1800));   // let the frontend's post-load view animation finish
  layoutBearGraph.fit(app);
  const r = await fetch(ud('workflows/bear/{name}.json') + '?overwrite=true',
    {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(app.graph.serialize()) }});
  return Object.assign({{ saved: r.status }}, report);
}})()"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("compiled", type=Path)
    ap.add_argument("--name", required=True, help="workflow name -> bear/<name>")
    ap.add_argument("--labels", type=Path, help="items.json: id -> tag (or string)")
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    ap.add_argument("--print-only", action="store_true", help="skip uploads, just print the bootstrap")
    a = ap.parse_args()

    if not a.compiled.is_file():
        sys.exit(f"publish: not found: {a.compiled}")
    labels = load_labels(a.labels)
    if not a.print_only:
        body = a.compiled.read_bytes()
        json.loads(body)  # fail early on a non-JSON file
        s1 = post_userdata(a.host, f"bear/{a.name}.api.json", body, "application/json")
        s2 = post_userdata(a.host, "bear/layout.js", (HERE / "layout.js").read_bytes(), "text/javascript")
        print(f"uploaded bear/{a.name}.api.json ({s1}) and bear/layout.js ({s2}) to {a.host}",
              file=sys.stderr)
    print(BOOTSTRAP.format(name=a.name, labels=json.dumps(labels)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
