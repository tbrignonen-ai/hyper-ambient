<#
.SYNOPSIS
  Deploie le BPMN night_health_vault_note sur Camunda 8.8 via REST API v2 (multipart),
  puis verifie par /v2/process-definitions/search que la definition est bien presente.

.NOTES
  Nuit MOTHER 2026-08-31. Aucun secret : le cluster local ecoute sans auth sur 127.0.0.1:8088.
#>
[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:8088',
    [string]$BpmnPath = (Join-Path $PSScriptRoot '..\..\resources\bpmn\night_health_vault_note.bpmn'),
    [string]$ProcessId = 'night_health_vault_note'
)

$ErrorActionPreference = 'Stop'
$BaseUrl = $BaseUrl.TrimEnd('/')

$bpmn = Resolve-Path -LiteralPath $BpmnPath
Write-Host "== BPMN     : $bpmn"
Write-Host "== Cluster  : $BaseUrl"

# --- 1. POST /v2/deployments (multipart, champ 'resources') -------------------
Write-Host "`n-- POST $BaseUrl/v2/deployments"
$deploy = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v2/deployments" `
    -Form @{ resources = Get-Item -LiteralPath $bpmn } `
    -TimeoutSec 60

$deploy | ConvertTo-Json -Depth 8

$deploymentKey = $deploy.deploymentKey
$definition = $deploy.deployments | ForEach-Object { $_.processDefinition } |
    Where-Object { $_ -and $_.processDefinitionId -eq $ProcessId } | Select-Object -First 1

if (-not $definition) {
    throw "Le deploiement n'a pas renvoye de processDefinition '$ProcessId'."
}

Write-Host "`n== deploymentKey        : $deploymentKey"
Write-Host "== processDefinitionKey : $($definition.processDefinitionKey)"
Write-Host "== version              : $($definition.version)"

# --- 2. POST /v2/process-definitions/search ----------------------------------
Write-Host "`n-- POST $BaseUrl/v2/process-definitions/search"
$searchBody = @{ filter = @{ processDefinitionId = $ProcessId } } | ConvertTo-Json -Depth 5
$search = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v2/process-definitions/search" `
    -ContentType 'application/json' -Body $searchBody -TimeoutSec 30

$search | ConvertTo-Json -Depth 8

$found = @($search.items | Where-Object { $_.processDefinitionId -eq $ProcessId })
if ($found.Count -lt 1) {
    throw "La definition '$ProcessId' est absente du resultat de recherche."
}
$smoke = @($search.items | Where-Object { $_.processDefinitionId -eq 'smoke_test' })
if ($smoke.Count -gt 0) {
    throw "La recherche a renvoye 'smoke_test' : filtre incorrect."
}

Write-Host "`nOK : '$ProcessId' deploye et distinct de smoke_test ($($found.Count) version(s))."

[pscustomobject]@{
    deploymentKey        = $deploymentKey
    processDefinitionKey = $definition.processDefinitionKey
    version              = $definition.version
    processDefinitionId  = $ProcessId
}
