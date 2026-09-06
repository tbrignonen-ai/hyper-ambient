<#
.SYNOPSIS
  Verifie l'execution de night_health_vault_note : etat de l'instance, incidents,
  et presence de la note de sante dans le coffre.

.NOTES
  Nuit MOTHER 2026-08-31. Lecture seule cote Camunda et cote coffre.
#>
[CmdletBinding()]
param(
    [string]$BaseUrl   = 'http://127.0.0.1:8088',
    [string]$ProcessId = 'night_health_vault_note',
    [string]$VaultDir  = 'C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights',
    [string]$NightDate = '2026-08-31',
    [int]$WaitSeconds  = 60
)

$ErrorActionPreference = 'Stop'
$BaseUrl = $BaseUrl.TrimEnd('/')

function Get-Instances {
    $body = @{ filter = @{ processDefinitionId = $ProcessId } } | ConvertTo-Json -Depth 5
    Invoke-RestMethod -Method Post -Uri "$BaseUrl/v2/process-instances/search" `
        -ContentType 'application/json' -Body $body -TimeoutSec 30
}

# --- 1. Attente d'un etat terminal (au plus WaitSeconds) ---------------------
Write-Host "-- POST $BaseUrl/v2/process-instances/search (filter processDefinitionId=$ProcessId)"
$deadline = (Get-Date).AddSeconds($WaitSeconds)
do {
    $result = Get-Instances
    $latest = $result.items | Sort-Object -Property startDate -Descending | Select-Object -First 1
    if ($latest -and $latest.state -ne 'ACTIVE') { break }
    Start-Sleep -Seconds 3
} while ((Get-Date) -lt $deadline)

$result | ConvertTo-Json -Depth 8

if (-not $latest) { throw "Aucune instance trouvee pour '$ProcessId'." }
Write-Host "`n== processInstanceKey : $($latest.processInstanceKey)"
Write-Host "== state              : $($latest.state)"
Write-Host "== hasIncident        : $($latest.hasIncident)"

# --- 2. Incidents -------------------------------------------------------------
Write-Host "`n-- POST $BaseUrl/v2/incidents/search"
$incBody = @{ filter = @{ processInstanceKey = $latest.processInstanceKey } } | ConvertTo-Json -Depth 5
$incidents = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v2/incidents/search" `
    -ContentType 'application/json' -Body $incBody -TimeoutSec 30
$incidents | ConvertTo-Json -Depth 8
$incidentCount = @($incidents.items).Count
Write-Host "== incidents          : $incidentCount"

# --- 3. Note de sante dans le coffre -----------------------------------------
$notePath = Join-Path $VaultDir "$NightDate-HEALTH.md"
$noteExists = Test-Path -LiteralPath $notePath
Write-Host "`n== note $notePath : $(if ($noteExists) { 'PRESENTE' } else { 'ABSENTE' })"
if ($noteExists) {
    Get-Content -LiteralPath $notePath -Encoding utf8
}

# --- 4. Verdict ---------------------------------------------------------------
$ok = ($latest.state -eq 'COMPLETED') -and ($incidentCount -eq 0) -and $noteExists
Write-Host "`n== VERDICT : $(if ($ok) { 'OK' } else { 'FAIL' })"

[pscustomobject]@{
    processInstanceKey = $latest.processInstanceKey
    state              = $latest.state
    incidents          = $incidentCount
    notePath           = $notePath
    noteExists         = $noteExists
    verdict            = if ($ok) { 'OK' } else { 'FAIL' }
}
