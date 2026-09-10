# Kill the port-8188 ComfyUI (if any) and relaunch it with live previews; wait until it answers.
#   powershell -NoProfile -File tools/relaunch.ps1 [-NoKill]
# Why: on this box a long Z-Image queue climbs the 160 GB system commit limit within one
# process (host staging grows per image); a fresh process between chunks costs ~20 s and
# avoids the silent death. See the comfy-local-ops skill.
param([switch]$NoKill)
$ErrorActionPreference = 'Continue'
if (-not $NoKill) {
  Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*main.py*' -and $_.CommandLine -like '*--port 8188*' } |
    ForEach-Object { "killing $($_.ProcessId)"; Stop-Process -Id $_.ProcessId -Force }
  Start-Sleep -Seconds 3
}
$a = @('--workspace','D:\tools\comfy\workspaces\default','launch','--','--port','8188',
  '--output-directory','D:\sync\Comfy','--input-directory','D:\sync\Comfy\input',
  '--models-directory','D:\comfyshared\ComfyModels','--fast','fp16_accumulation',
  '--use-sage-attention','--listen=0.0.0.0','--verbose','INFO','--log-stdout','--preview-method','auto')
$p = Start-Process 'C:\Users\hypnodroid\.local\bin\comfy.exe' -ArgumentList $a -WorkingDirectory 'D:\tools\comfy' -WindowStyle Minimized -PassThru
"launcher pid $($p.Id) at $(Get-Date -Format HH:mm:ss)"
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Seconds 3
  try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 'http://127.0.0.1:8188/system_stats'; if ($r.StatusCode -eq 200) { "up after $(($i+1)*3)s"; exit 0 } } catch {}
}
"server did not answer within 120 s"; exit 1
