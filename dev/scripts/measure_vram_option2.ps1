# Snapshot nvidia-smi pour l'option 2. Ne charge rien, ne tue rien.
# Ne touche pas serve_hostagent.py. Un unload Luciole n'est PAS fait ici.
#
#   powershell -File dev/scripts/measure_vram_option2.ps1
#   powershell -File dev/scripts/measure_vram_option2.ps1 -Phase Before
#   powershell -File dev/scripts/measure_vram_option2.ps1 -Phase After
#
# After n'a de sens que si Thomas/Claude a déjà rechargé llama-server
# sur MiniCPM. Cette lane Cursor C ne le fait pas (VRAM déjà ~9.5 Go).

param(
    [ValidateSet("Before", "After", "Now")]
    [string]$Phase = "Now"
)

$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"

Write-Host "phase=$Phase  stamp=$stamp"
Write-Host "note=snapshot seulement; verifier le modele actif separement"
Write-Host ""

Write-Host "=== gpu ==="
nvidia-smi --query-gpu=name,driver_version,memory.used,memory.free,memory.total,utilization.gpu --format=csv

Write-Host ""
Write-Host "=== compute apps ==="
nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv

Write-Host ""
Write-Host "=== pmon ==="
nvidia-smi pmon -c 1

if ($Phase -eq "After") {
    Write-Host ""
    Write-Host "si MiniCPM n'est pas le processus llama-server, ce snapshot n'est PAS la mesure option 2."
}
