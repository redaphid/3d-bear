# The machine this ran on ("soul") — what a future session needs to know

Measured 2026-09-10. Windows 11, RTX 4090 24 GB, 128 GB RAM, **system commit limit ≈ 160 GB** (this
number, not RAM, is what kills jobs). Everything below was paid for in lost hours.

## Three ComfyUI installs, three ports

| workspace | port | python / torch | purpose |
|---|---|---|---|
| `D:\tools\comfy\workspaces\default` | **8188** | 3.12.13 / torch 2.13.0+cu130 | the bear pipeline: Z-Image Turbo, Qwen-Image, Hunyuan3D 2.1, rembg |
| `D:\tools\comfy\workspaces\trellis` | **8190** | 3.12.13 / torch 2.10.0+cu130 | **TRELLIS.2** (ComfyUI-Trellis2 wrapper + its CUDA wheels). Separate because the wheels are built against torch 2.10 and fail on 2.13 with "procedure could not be found". Launch/stop: `start.ps1` in that workspace. Build details: `docs/TRELLIS2_EVAL.md`. |
| `D:\tools\comfy\workspaces\wkf` | 8189 | — | someone else's; never touch |

Shared by all: models `D:\comfyshared\ComfyModels`, outputs `D:\sync\Comfy`, inputs `D:\sync\Comfy\input`.
Never run generations on two of them at once.

**Launch 8188** (the only line that shows live previews and survives the commit limit):
```powershell
powershell -NoProfile -File tools/relaunch.ps1 -Extra '--fast-disk','--disable-pinned-memory','--cache-none','--reserve-vram','6'
```
`relaunch.ps1` kills the old port-8188 python, relaunches, waits for `/system_stats`. `--fast-disk
--disable-pinned-memory` keep model staging file-backed instead of pinned RAM (pinned memory was 52 GB
of commit); `--reserve-vram 6` leaves room for Ollama's runners so Hunyuan's decode stops thrashing.

**Submit jobs** with `python tools/submit.py <compiled.json…> --ids .comfy/<round>_ids.txt` (POSTs
`/prompt`, strips build.py's `_meta` key). `comfy --json run` leaves a python.exe behind per call — 90 in
one night.

## The commit limit (the cause of every "silent death")

Baseline with nothing running is ~114 GB: the WSL VM (`vmmemWSL`) holds ~55 GB, Ollama's runners up to
18 GB when loaded, the rest is the desktop. A fresh Z-Image process adds ~40 GB → 154 GB → the next
allocation dies with **no traceback, listener gone, process gone**. Signature: `curl` refuses (not a
timeout), `netstat` shows no LISTENING on 8188, the log ends mid-"prepared for dynamic VRAM loading".
The commit number you read afterwards looks innocent because the process is already dead.

- Log commit every 15 s while a job runs (`.comfy/guard.log`); a climb into the 150s means the next image dies.
- **Relaunch between Z-Image chunks** (fresh process each time) — the supervisor pattern in the
  bear-pipeline skill does this automatically and resubmits only the missing ids.
- Hunyuan3D and TRELLIS are fine (peak commit ~102–138 GB).
- Cures that need the user: `wsl --shutdown` (55 GB back) or a bigger pagefile.
- Keep exactly ONE memory guard running, and make it log the number it computes.

## Ollama keeps coming back — why (`docs/OLLAMA_ON_SOUL.md`)

A `pwsh` instance of `D:\Projects\ollama-proxy\supervise.ps1` (session 0, started at logon) restarts
`ollama serve` within ~24 s of any kill; disabling the scheduled tasks (`OllamaProxySupervisor`,
`OllamaAutoStart`, both now disabled) does not stop the loop already running. A warm client hits
`/api/generate` every 20 s and reloads `qwen3:4b-instruct` + `bge-m3` (5.8 GB VRAM, 18 GB commit).
`ollama stop <model>` unloads instantly without elevation; `.comfy/ollama_guard.ps1` does that every
10 s (run it detached with `-Minutes N`). Killing the supervisor and the server needs elevation. Ollama is
also bound to `0.0.0.0:11434` with inbound firewall rules and had traffic from an outside address — a
separate security decision for the owner.

## GPU budget (24 GB)

| model | VRAM | notes |
|---|---|---|
| Z-Image Turbo bf16 + Qwen3-4B encoder | 12.7 GB with `load_clip_device: cpu` | GPU encoder hangs in VAE decode when the card is contested |
| Qwen-Image 2512 fp8 | ~20 GB | only with Ollama truly down; 3.5 min/image |
| Hunyuan3D 2.1 | ~4–8 GB | 66 s/mesh at octree 256 |
| TRELLIS.2-4B (+ DINOv3) | ~14 GB peak with low_vram | 16 GB on disk; 8 min/mesh (DCx), 12 (HQ) with the SDPA attention fallback |
| Ollama runners when loaded | 5.8 GB | steal it back with the guard |

## Browser

Playwright MCP (`mcp__soul__playwright__*`) drives the user's Chrome; screenshots land in
`D:\Projects\playwright-mcp\`. ComfyUI's canvas draws blank boxes below ~60 % zoom — set 0.75+ after
`app.loadApiJson(queue_running[0][2])`. The browser is shared with other agents: stay on your own tab.

## Tool quirks

- `git rm`, `gh api` for repo settings and some `Stop-Process` calls are blocked by the permission
  classifier in this harness; GitHub Pages therefore has to be enabled by the user (Settings → Pages →
  `main` / `/docs`).
- A PowerShell command that greps for a script name will match **itself** and kill itself
  (exit 255); exclude `$PID` or build the pattern by concatenation.
- Bash heredocs containing an apostrophe fail in this harness; write a script file and run it.
- trimesh 5: `remove_degenerate_faces` is gone (`update_faces(nondegenerate_faces())`); the
  subdivision voxeliser needs ~13 GB on a decimated 240k-face mesh (`hollow.py` rasterises its own).
