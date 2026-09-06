<#
.SYNOPSIS
  Attend le temoin .worker-up (max 90 s) puis cree une instance de night_health_vault_note
  via POST /v2/process-instances.

.NOTES
  Nuit MOTHER 2026-08-31. Si le temoin est absent apres 90 s, le script sort en erreur
  SANS creer d'instance (regle de la nuit : pas d'instance sans worker).
  Aucun secret : les variables ne portent que des chemins et une URL locale.
#>
[CmdletBinding()]
param(
    [string]$BaseUrl      = 'http://127.0.0.1:8088',
    [string]$ProcessId    = 'night_health_vault_note',
    [string]$WorkerUpPath = (Join-Path $PSScriptRoot '..\..\workers\night_health_vault_note\.worker-up'),
    [int]$WaitSeconds     = 90,
    [string]$NightDate    = '2026-08-31',
    [string]$VaultDir     = 'C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights',
    [string]$TopologyUrl  = 'http://127.0.0.1:8088/v2/topology'
)

$ErrorActionPreference = 'Stop'
$BaseUrl = $BaseUrl.TrimEnd('/')

# --- 1. Attente du temoin worker ---------------------------------------------
Write-Host "-- Attente de $WorkerUpPath (max $WaitSeconds s)"
$deadline = (Get-Date).AddSeconds($WaitSeconds)
$workerUp = $false
while ((Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $WorkerUpPath) { $workerUp = $true; break }
    Start-Sleep -Seconds 2
}

if (-not $workerUp) {
    Write-Host "FAIL : .worker-up absent apres $WaitSeconds s -> aucune instance creee."
    throw "worker-up absent apres $WaitSeconds s"
}
Write-Host "OK : .worker-up detecte a $(Get-Date -Format o)."

# --- 2. POST /v2/process-instances -------------------------------------------
$body = @{
    processDefinitionId = $ProcessId
    variables = @{
        nightDate   = $NightDate
        vaultDir    = $VaultDir
        topologyUrl = $TopologyUrl
    }
} | ConvertTo-Json -Depth 6

Write-Host "`n-- POST $BaseUrl/v2/process-instances"
Write-Host $body

$instance = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v2/process-instances" `
    -ContentType 'application/json' -Body $body -TimeoutSec 60

$instance | ConvertTo-Json -Depth 8

Write-Host "`n== processInstanceKey : $($instance.processInstanceKey)"
$instance
