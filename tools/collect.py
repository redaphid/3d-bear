#!/usr/bin/env python
"""Mirror a ComfyUI output subfolder into the project and index it.

    python tools/collect.py <server_subdir> <project_dir> [--strip-counter] [--no-index]

    python tools/collect.py 3d-bear/stage2_mesh/round2       outputs/stage2_mesh/round2 --strip-counter
    python tools/collect.py debug/3d-bear/stage2_mesh/round2 outputs/stage2_mesh/round2 --strip-counter

<server_subdir> is relative to the ComfyUI output dir (COMFY_OUTPUT_DIR, default
D:/sync/Comfy). Files are copied byte-for-byte (shutil.copy2, so mtime survives)
because ComfyUI embeds the full API prompt in every PNG (tEXt `prompt`) and GLB
(asset.extras.prompt) — the copies stay re-loadable workflow states. A file is
skipped when the destination already has the same size and mtime.

--strip-counter renames ComfyUI's `<name>_00001_.<ext>` to `<name>.<ext>`; a
later counter (`_00002_`) becomes `<name>-2.<ext>` so re-runs never clobber.

The index: `<project_dir>/index.md` gets a table of EVERY file in the dir with a
one-line summary read from the embedded prompt (seed / steps / cfg / octree /
threshold / source image, plus tri count + watertight for meshes). Only the
block between `<!-- collect:begin -->` and `<!-- collect:end -->` is rewritten;
anything else in the file (e.g. an appended mesh report) is preserved.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import sys
from pathlib import Path

SERVER_OUT = Path(os.environ.get("COMFY_OUTPUT_DIR", "D:/sync/Comfy"))
COUNTER_RE = re.compile(r"^(?P<stem>.+?)_(?P<n>\d{5})_(?P<ext>\.[^.]+)$")
BEGIN, END = "<!-- collect:begin -->", "<!-- collect:end -->"


def target_name(name: str, strip: bool) -> str:
    m = COUNTER_RE.match(name)
    if not strip or not m:
        return name
    n = int(m.group("n"))
    suffix = "" if n == 1 else f"-{n}"
    return f"{m.group('stem')}{suffix}{m.group('ext')}"


def same_file(src: Path, dst: Path) -> bool:
    if not dst.exists():
        return False
    a, b = src.stat(), dst.stat()
    return a.st_size == b.st_size and int(a.st_mtime) == int(b.st_mtime)


def copy_new(src_dir: Path, dst_dir: Path, strip: bool) -> list[Path]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in sorted(src_dir.iterdir()):
        if not src.is_file():
            continue
        dst = dst_dir / target_name(src.name, strip)
        if same_file(src, dst):
            continue
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


# ---- embedded metadata -------------------------------------------------------

def prompt_from_png(path: Path) -> dict | None:
    try:
        from PIL import Image
        with Image.open(path) as im:
            raw = (getattr(im, "text", None) or {}).get("prompt")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def prompt_from_glb(path: Path) -> dict | None:
    try:
        with open(path, "rb") as f:
            magic, _ver, _len = struct.unpack("<III", f.read(12))
            if magic != 0x46546C67:
                return None
            clen, ctype = struct.unpack("<II", f.read(8))
            if ctype != 0x4E4F534A:
                return None
            gltf = json.loads(f.read(clen))
        raw = ((gltf.get("asset") or {}).get("extras") or {}).get("prompt")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def embedded_prompt(path: Path) -> dict | None:
    ext = path.suffix.lower()
    if ext == ".png":
        return prompt_from_png(path)
    if ext in (".glb", ".gltf"):
        return prompt_from_glb(path)
    return None


def summarize_prompt(prompt: dict) -> str:
    """One line of the settings that matter, pulled by class_type — never by node id."""
    bits: list[str] = []
    by_class: dict[str, list[dict]] = {}
    for node in prompt.values():
        if isinstance(node, dict) and "class_type" in node:
            by_class.setdefault(node["class_type"], []).append(node.get("inputs") or {})

    def first(cls: str) -> dict:
        return (by_class.get(cls) or [{}])[0]

    ks = first("KSampler")
    for key in ("seed", "steps", "cfg"):
        if key in ks and not isinstance(ks[key], list):
            bits.append(f"{key}={ks[key]}")
    vd = first("VAEDecodeHunyuan3D")
    if "octree_resolution" in vd:
        bits.append(f"octree={vd['octree_resolution']}")
    vm = first("VoxelToMesh")
    if "threshold" in vm:
        bits.append(f"thr={vm['threshold']}")
    if vm.get("algorithm") and vm["algorithm"] != "surface net":
        bits.append(f"alg={vm['algorithm']}")
    lat = first("EmptySD3LatentImage")
    if "width" in lat and "height" in lat:
        bits.append(f"{lat['width']}x{lat['height']}")
    srcs = [n.get("image") for n in by_class.get("LoadImage", []) if isinstance(n.get("image"), str)]
    if srcs:
        bits.append("src=" + ",".join(srcs))
    if "Image Remove Background (rembg)" in by_class:
        bits.append("rembg")
    return " ".join(bits) if bits else "(no recognised nodes)"


def mesh_stats(path: Path) -> str:
    try:
        import trimesh
        m = trimesh.load(path, force="mesh")
        if isinstance(m, trimesh.Scene):
            m = trimesh.util.concatenate(m.dump())
        wt = "yes" if m.is_watertight else "no"
        return f"tris={len(m.faces):,} watertight={wt}"
    except Exception as e:  # trimesh missing or unreadable file — the index still lists it
        return f"(mesh unreadable: {type(e).__name__})"


def describe(path: Path) -> str:
    parts = []
    if path.suffix.lower() in (".glb", ".gltf", ".obj", ".stl"):
        parts.append(mesh_stats(path))
    prompt = embedded_prompt(path)
    parts.append(summarize_prompt(prompt) if prompt else "(no embedded prompt)")
    return " · ".join(parts)


# ---- index -------------------------------------------------------------------

def render_table(project_dir: Path) -> str:
    rows = ["| file | size | summary |", "|---|---|---|"]
    for p in sorted(project_dir.iterdir()):
        if not p.is_file() or p.name == "index.md":
            continue
        size = p.stat().st_size
        human = f"{size / 1e6:.1f} MB" if size >= 1e6 else f"{size / 1e3:.0f} kB"
        rows.append(f"| [{p.name}]({p.name}) | {human} | {describe(p)} |")
    return "\n".join(rows)


def write_index(project_dir: Path, server_subdir: str) -> Path:
    idx = project_dir / "index.md"
    block = (f"{BEGIN}\n_Auto-generated by `tools/collect.py` from `{server_subdir}` "
             f"(and any other server dirs collected here). Do not edit inside these markers._\n\n"
             f"{render_table(project_dir)}\n{END}")
    if idx.exists():
        text = idx.read_text(encoding="utf-8")
        if BEGIN in text and END in text:
            pre, rest = text.split(BEGIN, 1)
            _, post = rest.split(END, 1)
            text = pre + block + post
        else:
            text = text.rstrip() + "\n\n" + block + "\n"
    else:
        title = " / ".join(project_dir.as_posix().rstrip("/").split("/")[-2:])
        text = f"# {title}\n\n{block}\n"
    idx.write_text(text, encoding="utf-8")
    return idx


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("server_subdir", help="path under the ComfyUI output dir")
    ap.add_argument("project_dir", help="destination dir in the project")
    ap.add_argument("--strip-counter", action="store_true", help="drop ComfyUI's _0000N_ suffix")
    ap.add_argument("--no-index", action="store_true", help="copy only; do not touch index.md")
    a = ap.parse_args()

    src_dir = SERVER_OUT / a.server_subdir
    dst_dir = Path(a.project_dir)
    if not src_dir.is_dir():
        print(f"collect: nothing at {src_dir} yet")
        return 0
    copied = copy_new(src_dir, dst_dir, a.strip_counter)
    for c in copied:
        print(f"collect: + {c.as_posix()}")
    if not copied:
        print(f"collect: {a.server_subdir}: nothing new")
    if not a.no_index:
        idx = write_index(dst_dir, a.server_subdir)
        print(f"collect: index -> {idx.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
