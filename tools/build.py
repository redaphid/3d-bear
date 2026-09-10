#!/usr/bin/env python
"""Compiler driver for blueprints: compose -> tap pass -> validate.

    python tools/build.py blueprints/<name>.yaml [--debug] [--no-validate]

This is a *compiler pass*, not a hand-edit of the compiled JSON. The source of
truth stays in fragments/ and blueprints/; this script runs
`comfy workflow compose`, then rewrites the artifact it produced in place so
that `comfy run --workflow blueprints/<name>.compiled.json` keeps working
unchanged. Never edit the compiled file by hand — change the blueprint and
rebuild.

The tap convention
------------------
A "tap" is any SaveImage / SaveGLB node whose `filename_prefix` starts with
`debug/` (see fragments/tap_image.json and fragments/tap_mesh.json). Taps are
debug probes wired onto intermediates. By default this pass REMOVES them from
the compiled graph and prunes their ids from `_meta.items[*].nodes`, so the
runnable artifact is exactly the deliverable graph. `--debug` keeps them so a
run also writes every intermediate under output/debug/.

What the pass records in `_meta`
--------------------------------
    debug     bool      whether taps were kept
    built_at  ISO-8601  UTC timestamp of this build
    taps      {kept: [ids], stripped: [ids]}   for the UI / provenance

Chunked blueprints (`chunk: N`) produce several files; every one goes through
the same pass. Exit status is non-zero if compose, the tap pass, or validation
fails, and the error's `hint` from the CLI envelope is printed.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TAP_CLASSES = {"SaveImage", "SaveGLB"}
TAP_PREFIX = "debug/"


def find_project_root(start: Path) -> Path:
    """Walk up from `start` to the directory holding comfy.yaml."""
    for d in [start] + list(start.parents):
        if (d / "comfy.yaml").is_file():
            return d
    sys.exit(f"build: no comfy.yaml above {start} — run inside a comfy project")


def comfy_json(args: list[str], cwd: Path) -> dict:
    """Run `comfy --json <args>` and return the envelope; exit on failure."""
    exe = shutil.which("comfy")
    if not exe:
        sys.exit("build: `comfy` not found on PATH")
    proc = subprocess.run(
        [exe, "--json", *args], cwd=str(cwd), capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-15:]
        sys.exit("build: comfy %s did not return JSON (exit %d):\n  %s"
                 % (" ".join(args), proc.returncode, "\n  ".join(tail)))
    if not env.get("ok"):
        err = env.get("error") or {}
        msg = f"build: comfy {' '.join(args)} failed: {err.get('code')}: {err.get('message')}"
        if err.get("hint"):
            msg += f"\n  hint: {err['hint']}"
        sys.exit(msg)
    return env


def is_tap(node: dict) -> bool:
    if node.get("class_type") not in TAP_CLASSES:
        return False
    prefix = node.get("inputs", {}).get("filename_prefix")
    return isinstance(prefix, str) and prefix.startswith(TAP_PREFIX)


def tap_pass(path: Path, keep_taps: bool) -> tuple[int, list[str], list[str]]:
    """Strip (or keep) tap nodes in one compiled file. Returns (nodes, kept, stripped)."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    meta = doc.setdefault("_meta", {})
    node_ids = [k for k in doc if k != "_meta"]
    taps = [k for k in node_ids if is_tap(doc[k])]

    # A tap must be a leaf. If anything consumes a tap's output, stripping it
    # would tear the graph — refuse rather than emit a broken artifact.
    for k in node_ids:
        for v in doc[k].get("inputs", {}).values():
            if isinstance(v, list) and len(v) == 2 and str(v[0]) in taps:
                sys.exit(f"build: {path.name}: node {k} consumes tap {v[0]}; taps must be leaves")

    kept, stripped = (taps, []) if keep_taps else ([], taps)
    for k in stripped:
        del doc[k]
    for item in (meta.get("items") or {}).values():
        item["nodes"] = [n for n in item.get("nodes", []) if n not in stripped]

    meta["debug"] = keep_taps
    meta["built_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    meta["taps"] = {"kept": kept, "stripped": stripped}
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return len(doc) - 1, kept, stripped


def validate(path: Path, root: Path) -> tuple[bool, str]:
    env = comfy_json(["validate", "--workflow", str(path)], root)
    data = env.get("data") or {}
    valid = bool(data.get("valid", True))
    detail = ""
    problems = data.get("errors") or []
    if problems:
        detail = "; ".join(f"{p.get('node_id')}.{p.get('field')}: {p.get('message')}"
                           if isinstance(p, dict) else str(p) for p in problems[:5])
    nwarn = data.get("warning_count") or len(data.get("warnings") or [])
    if nwarn:
        detail = (detail + " " if detail else "") + f"({nwarn} warnings)"
    return valid, detail


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("blueprint", type=Path)
    ap.add_argument("--debug", action="store_true", help="keep debug taps in the artifact")
    ap.add_argument("--no-validate", action="store_true", help="skip `comfy validate`")
    ap.add_argument("--lib", help="fragment library dir (default ./fragments)")
    ap.add_argument("-o", "--out", help="output path (default <blueprint>.compiled.json)")
    a = ap.parse_args()

    bp = a.blueprint.resolve()
    if not bp.is_file():
        sys.exit(f"build: blueprint not found: {bp}")
    root = find_project_root(bp.parent)

    args = ["workflow", "compose", os.path.relpath(bp, root)]
    if a.lib:
        args += ["--lib", a.lib]
    if a.out:
        args += ["--out", a.out]
    env = comfy_json(args, root)
    data = env["data"]
    written = data.get("written") or ([data["out"]] if data.get("out") else [])
    if not written:
        sys.exit("build: compose wrote nothing")

    failed = False
    for w in written:
        path = Path(w) if os.path.isabs(w) else root / w
        n, kept, stripped = tap_pass(path, keep_taps=a.debug)
        if a.no_validate:
            status = "valid=skipped"
        else:
            ok, detail = validate(path, root)
            status = f"valid=yes {detail}".rstrip() if ok else f"valid=NO {detail}"
            failed |= not ok
        print(f"{os.path.relpath(path, root)}: {n} nodes, taps kept={len(kept)} "
              f"stripped={len(stripped)}, {status}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
