#!/usr/bin/env python
"""Submit compiled workflows straight to ComfyUI over HTTP.

    python tools/submit.py blueprints/stage1_refs_round3z.compiled.00[1-3].json [--ids .comfy/round3z_ids.txt]

Why not `comfy run`: on this box every `comfy --json run` left a python.exe
behind (about 90 of them in one night), and the CLI has no --no-wait. POST
/prompt is what it does anyway. build.py's `_meta` key is stripped here —
ComfyUI rejects it as a node without class_type.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime


def submit(host: str, path: str, client_id: str) -> str:
    g = json.load(open(path, encoding="utf-8"))
    g.pop("_meta", None)
    body = json.dumps({"prompt": g, "client_id": client_id}).encode()
    req = urllib.request.Request(f"{host}/prompt", data=body, headers={"Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=180))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{path}: HTTP {e.code} {e.read().decode()[:600]}")
    if r.get("node_errors"):
        raise SystemExit(f"{path}: node_errors {json.dumps(r['node_errors'])[:600]}")
    return r["prompt_id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="compiled API-format JSON files (globs ok)")
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    ap.add_argument("--ids", help="append 'prompt_id  file  time' lines to this registry file")
    ap.add_argument("--client-id", default="submit.py")
    a = ap.parse_args()
    paths = [p for pat in a.files for p in (sorted(glob.glob(pat)) or [pat])]
    out = []
    for p in paths:
        pid = submit(a.host, p, a.client_id)
        print(f"{pid}  {p}")
        out.append(f"{pid}  {p}  {datetime.now():%Y-%m-%d %H:%M}\n")
    if a.ids:
        with open(a.ids, "a", encoding="utf-8") as f:
            f.writelines(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
