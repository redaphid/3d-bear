# Ollama on soul: why it keeps coming back

Read-only investigation, 2026-09-10 ~02:00. Nothing was stopped, killed or changed.
All PIDs below are from that window and will not survive a restart.

## Short answer

A **still-running supervisor loop** restarts Ollama, and a **client hitting port 11434 every
20 seconds** reloads the models. These are two different mechanisms, and disabling the
scheduled tasks defeated neither.

The supervisor is `D:\Projects\ollama-proxy\supervise.ps1`, running as `pwsh.exe` PID 14096
since 2026-09-09 15:22:31. It was launched by the `OllamaProxySupervisor` scheduled task
*before* that task was disabled. Disabling a task does not terminate an instance that is
already running, and this script never exits: its main body is `while ($true)`.

---

## (a) Process tree and who launches the SYSTEM Ollama

```
pwsh.exe            PID 14096   session 0   started 2026-09-09 15:22:19
  |                             running D:\Projects\ollama-proxy\supervise.ps1
  +-- ollama.exe     PID 31852  session 0   started 2026-09-10 00:13:04  LISTENING 0.0.0.0:11434
  |     +-- llama-server.exe PID 37952      started 2026-09-10 01:57:17
  +-- python.exe     PID 26632  session 0   started 2026-09-09 15:23:08  (proxy.py supervisor child)
        +-- python.exe PID 27036            ESTABLISHED to 127.0.0.1:11434
```

Evidence, `D:\Projects\ollama-proxy\supervisor-11436.log`, last lines:

```
2026-09-09 15:22:31 supervisor up (port=11436 upstream=http://127.0.0.1:11434 dir=D:\Projects\ollama-proxy)
2026-09-09 15:23:05 adopted ollama already answering on 11434 (pid 14584) -- not starting a second one
2026-09-09 15:23:08 started proxy on 11436 -> http://127.0.0.1:11434 (pid 26632, ...)
2026-09-10 00:13:02 ollama on 11434 not answering http://127.0.0.1:11434/api/tags
2026-09-10 00:13:04 started ollama serve on 11434 (pid 31852)
2026-09-10 00:13:24 ollama on 11434 is answering again
```

That 00:13 entry is the elevated kill from earlier in the night being undone. The loop polls
every 20 seconds (`$PollSec = 20`) and calls `Invoke-OllamaWatch` on every pass. Measured
recovery is roughly 24 seconds.

**The binary it starts is the desktop app's, not the portable one.** `supervise.ps1` defines:

```powershell
[string] $OllamaExe = (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe')
```

which resolves to `C:\Users\hypnodroid\AppData\Local\Programs\Ollama\ollama.exe`.
`D:\tools\ollama\bin\ollama.exe` is **not** what is running. The behaviour of
`serve-main.cmd` (Idle priority watchdog, explicit flash-attention) is therefore **not in
effect**; the process instead inherits the user environment variables:

| Variable | Value |
|---|---|
| `OLLAMA_HOST` | `0.0.0.0:11434` |
| `OLLAMA_MODELS` | `D:\tools\ollama` |
| `OLLAMA_FLASH_ATTENTION` | `true` |
| `OLLAMA_KEEP_ALIVE` | `30m` |

The 30-minute keep-alive seen in `ollama ps` comes from that user variable, not from a script.

There is no Windows service and no NSSM. `Get-Service` returns nothing Ollama-related.

## (b) The clients

Two separate clients appear in `D:\Projects\ollama-proxy\ollama-11434.out.log`. Counts over
the whole current log file:

| Client | Requests |
|---|---|
| `127.0.0.1` | 662 |
| `98.165.4.2` | 456 |

**The reloader is the 127.0.0.1 client.** Every 20 seconds it issues the same sequence:

```
HEAD "/"  ->  GET "/api/ps"  ->  HEAD "/"  ->  POST "/api/show"  ->  POST "/api/generate"
```

The `/api/generate` completes in 2 to 9 ms, so it carries no real prompt. That is a model
**warm/keepalive** call: it reloads an unloaded model and resets the 30-minute timer. This is
what beats `ollama stop`, and it matches the 20-second cadence in
`D:\Projects\3d-bear\.comfy\ollama_guard.log` exactly.

**The heavy client is 98.165.4.2**, doing real `POST /api/generate` (14 s to 1 m 34 s) and
`POST /api/embed`. That is not a local address. `Get-NetIPAddress` on soul lists only
`10.0.136.62`, `172.21.48.1`, `100.89.135.38` (Tailscale) and link-local addresses. Ollama is
bound to `0.0.0.0:11434` and there are **two enabled inbound firewall rules opening TCP
11434**, so this traffic is arriving over the network.

**Configuration locations**

- Mindmeld's Docker services (`mindmeld-sync`, `mindmeld-sync-machines`, `mindmeld-mcp`,
  `mindmeld-centroids`) are all configured with
  `OLLAMA_URL=http://host.docker.internal:11436`, `EMBEDDING_MODEL=bge-m3`,
  `SUMMARIZE_MODEL=qwen3:4b-instruct` (verified by `docker inspect`, and in
  `D:\Projects\mind-meld\.env` line 18).
- So mindmeld goes through the **gate proxy on 11436**, not directly to 11434.
- The proxy is currently **refusing that work**. `proxy-11436.out.log` shows repeated
  `POST /api/embed ... 503 Service Unavailable`. `/api/generate`, `/api/chat`, `/api/embed`
  and the `/v1/*` routes are in the `GATED` set in `proxy.py`; `/api/tags`, `/api/ps` and
  `/api/show` pass straight through.
- The default in `D:\Projects\mind-meld\src\config.ts:119` is
  `getEnv("OLLAMA_URL", "http://127.0.0.1:11434")` — anything running that code **without**
  the env var set bypasses the gate entirely.

## (c) Minimal commands to stop it for a night, and to restore it

**Do not run these yet — listed for the user's decision. Order matters.**

Stop, in this order (steps 1 and 2 need no elevation; step 3 does, because the targets are
session-0 processes):

```powershell
# 1. Keep the 15-minute self-heal trigger from re-launching it (already Disabled today).
Disable-ScheduledTask -TaskName OllamaProxySupervisor

# 2. Kill the supervisor loop FIRST, or it restarts ollama within ~24 s.
Stop-Process -Id 14096 -Force          # pwsh running supervise.ps1  -- NEEDS ELEVATION

# 3. Then the server it left behind, as a tree (llama-server is its child).
taskkill /PID 31852 /T /F              # ollama.exe               -- NEEDS ELEVATION
taskkill /PID 26632 /T /F              # proxy.py                 -- NEEDS ELEVATION
```

Also required, or the models come straight back: **stop the 20-second warm client.** It has
not been positively identified (see below). The blunt, reversible option is to stop the
mindmeld containers, which is not elevated:

```powershell
wsl -d survivor -- docker stop mindmeld-sync mindmeld-sync-machines mindmeld-mcp mindmeld-centroids
```

Restore:

```powershell
wsl -d survivor -- docker start mindmeld-sync mindmeld-sync-machines mindmeld-mcp mindmeld-centroids
Enable-ScheduledTask -TaskName OllamaProxySupervisor
Start-ScheduledTask  -TaskName OllamaProxySupervisor
Get-Content D:\Projects\ollama-proxy\supervisor-11436.log -Tail 20
```

The supervisor brings Ollama and the proxy back up by itself; nothing else needs starting.
Leave `OllamaAutoStart` and `OllamaEmbedFAoff` disabled — they belong to the older
`D:\tools\ollama` layout that is not in use.

Verification probes: `curl http://127.0.0.1:11436/_gate` and `curl http://127.0.0.1:11434/api/tags`.

## (d) Things that contradict the assumptions in the brief

1. **It is not running as SYSTEM in the sense of a service.** It is a session-0 process, but
   there is no service and no NSSM. `$env:LOCALAPPDATA` resolved to hypnodroid's profile
   (that is how it found the desktop-app binary), so the supervisor is running with the
   user's profile via the task's S4U configuration, not as the machine account.
   `C:\Windows\System32\config\systemprofile\AppData\Local\Ollama` does not exist.
2. **The disabled scheduled tasks were never the live cause.** `OllamaProxySupervisor` last
   ran at 00:01:01 and returned `267014` ("task not running"). The supervisor that matters
   has been alive since 15:22 on 2026-09-09 and is immune to the task being disabled.
3. **The running binary is the desktop app's `ollama.exe`, not `D:\tools\ollama\bin\ollama.exe`.**
   The two-installs collision has reversed from what earlier sessions documented: the
   supervisor's headless copy now owns 11434, and the tray app is the loser.
   `%LOCALAPPDATA%\Ollama\server.log` is filled with
   `Error: listen tcp 0.0.0.0:11434: bind: Only one usage of each socket address ... is normally permitted.`
4. **Mindmeld is not the thing hammering 11434.** It is pointed at the proxy on 11436 and is
   currently being refused with 503s. Something else is reaching 11434 directly.
5. **The heavy traffic is not local.** 456 requests came from `98.165.4.2`, a non-local
   address, against an interface deliberately bound to `0.0.0.0` with inbound firewall rules
   open. Worth a decision on its own merits, separate from tonight's VRAM problem.

## What I could not determine

- **The exact identity of the 20-second warm client.** Sampling `Get-NetTCPConnection` for 45
  seconds showed only two processes ever connected to 11434: `com.docker.backend.exe`
  (PID 30176) and the proxy's `python.exe` (PID 27036). The warm calls appear at Ollama as
  `127.0.0.1`, which is consistent with a **Docker container reaching
  `host.docker.internal:11434`** and being forwarded by the Docker backend. No running
  container declares 11434 in its environment, and no container log mentions Ollama in the
  last 3 minutes, so I could not name it. `docker ps` from Windows fails with an API version
  mismatch (500 from the `dockerDesktopLinuxEngine` pipe); I worked around it through
  `wsl -d survivor -- docker`.
- **Where 98.165.4.2 is.** I did not probe outward to identify it.
- **Why the three Ollama tasks are disabled and by whom.** Not recorded anywhere I looked.
- **What started PID 14096 at 15:22 on 2026-09-09.** The parent PID 12676 is dead, so the
  chain cannot be walked. The box had booted 31 seconds earlier (the supervisor logged
  `booted 31s ago`), so a logon trigger is the likely origin, from before the task was disabled.
- Command lines for the session-0 processes are not readable without elevation; their
  identities above are established from parent/child relationships and the supervisor's own log.

## Sources

- `D:\Projects\ollama-proxy\supervise.ps1` (the loop, the parameters, the ollama watch)
- `D:\Projects\ollama-proxy\supervisor-11436.log` (restart events)
- `D:\Projects\ollama-proxy\ollama-11434.out.log` (per-request client IPs and routes)
- `D:\Projects\ollama-proxy\proxy-11436.out.log` (the 503s)
- `D:\Projects\ollama-proxy\proxy.py` (the `GATED` set)
- `D:\Projects\mind-meld\.env`, `docker-compose.yml`, `docker-compose.override.yml`, `src/config.ts`
- `C:\Users\hypnodroid\AppData\Local\Ollama\server.log` (bind failures of the tray app)
- `C:\Users\hypnodroid\.local\bin\hidden-OllamaProxySupervisor.vbs`
- `D:\tools\ollama\serve-main.cmd`, `serve-embed.cmd`, `start-main.vbs` (the older, unused path)
- `D:\Projects\3d-bear\.comfy\ollama_guard.log` (the 20-second unload cadence)
