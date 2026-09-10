#!/usr/bin/env python
"""Push project assets and repair the lock that `comfy assets push` fails to write.

    python tools/push_assets.py [--no-push]

On Windows `comfy --json assets push` uploads every new/changed file under
assets/, writes the complete lock to `.comfy/assets.lock.<pid>.tmp`, then dies
on os.fsync before renaming it over `.comfy/assets.lock.json`. Compose reads
only the real lock, so the pushed files stay invisible as `$asset` refs.

This script runs the push (its non-zero exit is ignored), then MERGES every
`.comfy/assets.lock.*.tmp` into `.comfy/assets.lock.json`: the union of the
`assets` dicts, oldest tmp first so the newest entry for a path wins, on top of
whatever the real lock already holds. Other agents push concurrently, so the
lock is re-read immediately before the merged result is written and the write
itself is atomic (tmp + os.replace). A tmp that is still being written (not yet
valid JSON) is left alone for the next run. Merged tmps are deleted.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_project_root(start: Path) -> Path:
    for d in [start] + list(start.parents):
        if (d / "comfy.yaml").is_file():
            return d
    sys.exit(f"push_assets: no comfy.yaml above {start}")


def run_push(root: Path) -> None:
    exe = shutil.which("comfy")
    if not exe:
        sys.exit("push_assets: `comfy` not found on PATH")
    proc = subprocess.run([exe, "--json", "assets", "push"], cwd=str(root),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        env = json.loads(proc.stdout)
        data = env.get("data") or {}
        pushed = data.get("pushed") or data.get("uploaded") or []
        n = len(pushed) if isinstance(pushed, list) else pushed
        print(f"push_assets: comfy assets push ok={env.get('ok')} pushed={n}")
        if not env.get("ok") and env.get("error"):
            err = env["error"]
            print(f"push_assets: push error (continuing): {err.get('code')}: {err.get('message')}")
    except json.JSONDecodeError:
        # The fsync crash produces a traceback, not an envelope. Expected on Windows.
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["<no output>"]
        print(f"push_assets: comfy assets push exited {proc.returncode} without an envelope ({tail[0][:120]})")


def load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def merge_locks(root: Path) -> None:
    comfy_dir = root / ".comfy"
    lock_path = comfy_dir / "assets.lock.json"
    tmps = sorted(comfy_dir.glob("assets.lock.*.tmp"), key=lambda p: p.stat().st_mtime)
    if not tmps:
        print("push_assets: no tmp locks to merge")
        return

    merged_from: list[Path] = []
    incoming: dict = {}
    for t in tmps:
        doc = load_json(t)
        if not doc or not isinstance(doc.get("assets"), dict):
            print(f"push_assets: skipping {t.name} (not valid JSON yet)")
            continue
        incoming.update(doc["assets"])  # newest tmp overwrites older entries
        merged_from.append(t)
    if not incoming:
        return

    # Re-read the real lock right before writing so a concurrent merge is not lost.
    current = load_json(lock_path) or {"schema": "assets-lock/1", "assets": {}}
    assets = dict(current.get("assets") or {})
    before = len(assets)
    assets.update(incoming)
    current["assets"] = dict(sorted(assets.items()))
    current.setdefault("schema", "assets-lock/1")

    out = lock_path.with_name(f"assets.lock.merge.{os.getpid()}")
    out.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    os.replace(out, lock_path)
    for t in merged_from:
        try:
            t.unlink()
        except OSError:
            pass
    print(f"push_assets: merged {len(merged_from)} tmp lock(s): {before} -> {len(assets)} entries "
          f"in {lock_path.relative_to(root).as_posix()}")
    for k in sorted(incoming):
        print(f"  {k} -> {incoming[k].get('cloud_name')}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-push", action="store_true", help="only merge existing tmp locks")
    a = ap.parse_args()
    root = find_project_root(Path.cwd())
    if not a.no_push:
        run_push(root)
    merge_locks(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
