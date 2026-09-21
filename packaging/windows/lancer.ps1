# Lanceur Windows d'hyper-ambient.
# Il ne cree, n'installe ni ne reconfigure rien : installer.ps1 -Diagnostic
# explique les prealables manquants. Chaque demarrage est precede d'un controle.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$script:delaiDockerSec = 60
$script:delaiServiceSec = 45
$script:manques = New-Object System.Collections.Generic.List[string]

function Dire {
    param([string]$Ligne)
    Write-Host $Ligne
}

function Ajouter-Manque {
    param([string]$Texte)
    [void]$script:manques.Add($Texte)
}

function Docker-Repond {
    $commande = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $commande) { return $false }
    try {
        $null = & $commande.Source info 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Chemin-DockerDesktop {
    $candidats = @(
        (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Docker\Docker\Docker Desktop.exe')
    )
    foreach ($candidat in $candidats) {
        if ($candidat -and (Test-Path -LiteralPath $candidat)) { return $candidat }
    }
    return $null
}

function Attendre {
    param([scriptblock]$Condition, [int]$Secondes)
    $limite = (Get-Date).AddSeconds($Secondes)
    while ((Get-Date) -lt $limite) {
        if (& $Condition) { return $true }
        Start-Sleep -Seconds 1
    }
    return (& $Condition)
}

function Port-Repond {
    param([int]$Port)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $attente = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $attente.AsyncWaitHandle.WaitOne(1500)) { return $false }
        $client.EndConnect($attente)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Etat-Conteneur {
    $etat = & docker inspect -f '{{.State.Status}}' mother-core-dev 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return ($etat | Out-String).Trim()
}

function Processus-Presence {
    try {
        # Le jeu de proprietes CIM par defaut de Windows PowerShell 5.1 peut
        # omettre CommandLine. Cette requete WMI demande explicitement les deux
        # proprietes, et donne le meme resultat avec Windows PowerShell et
        # PowerShell 7.
        $requete = New-Object System.Management.ManagementObjectSearcher(
            "SELECT ProcessId, CommandLine FROM Win32_Process WHERE Name = 'pythonw.exe' OR Name = 'python.exe'"
        )
        return @($requete.Get() | Where-Object { $_.CommandLine -match 'native[\\/]presence[\\/]app\.py' })
    } catch {
        return @()
    }
}

function Demarrer-Docker {
    if (Docker-Repond) {
        Dire 'Docker : deja en service.'
        return $true
    }
    $dockerDesktop = Chemin-DockerDesktop
    if (-not $dockerDesktop) {
        Dire 'Docker : absent ou lanceur introuvable.'
        Ajouter-Manque 'Docker Desktop manque ou ne peut pas etre lance. Executez installer.ps1 -Diagnostic.'
        return $false
    }
    Dire "Docker : demarrage de `"$dockerDesktop`" (attente maximale : $($script:delaiDockerSec) s)."
    Start-Process -FilePath $dockerDesktop | Out-Null
    if (Attendre -Condition ${function:Docker-Repond} -Secondes $script:delaiDockerSec) {
        Dire 'Docker : pret.'
        return $true
    }
    Dire "Docker : delai depasse apres $($script:delaiDockerSec) s. Acceptez sa licence ou corrigez Docker Desktop, puis relancez."
    Ajouter-Manque 'Docker ne repond pas. Verifiez Docker Desktop, puis relancez le lanceur.'
    return $false
}

function Demarrer-Conteneur {
    $etat = Etat-Conteneur
    if ($etat -eq 'running') {
        Dire 'mother-core-dev : deja en service.'
        return $true
    }
    if (-not $etat) {
        Dire 'mother-core-dev : conteneur absent ; je ne le cree pas.'
        Ajouter-Manque 'mother-core-dev est absent. Executez installer.ps1 -Diagnostic.'
        return $false
    }
    Dire "mother-core-dev : etat $etat ; docker start sans recreation."
    & docker start mother-core-dev | Out-Null
    if ($LASTEXITCODE -eq 0 -and (Attendre -Condition { (Etat-Conteneur) -eq 'running' } -Secondes 15)) {
        Dire 'mother-core-dev : pret.'
        return $true
    }
    Dire 'mother-core-dev : echec au demarrage ; consultez docker logs mother-core-dev.'
    Ajouter-Manque 'mother-core-dev ne demarre pas. Consultez docker logs mother-core-dev.'
    return $false
}

function Demarrer-ServeurModele {
    param([string]$Nom, [int]$Port, [string]$Script)
    if (Port-Repond -Port $Port) {
        Dire "$Nom : deja en service (127.0.0.1:$Port)."
        return $true
    }
    Dire "$Nom : demarrage dans mother-core-dev (port $Port)."
    & docker exec -d mother-core-dev bash $Script | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Dire "$Nom : commande de demarrage refusee."
        Ajouter-Manque "$Nom ne demarre pas. Consultez docker logs mother-core-dev et les modeles locaux."
        return $false
    }
    if (Attendre -Condition { Port-Repond -Port $Port } -Secondes $script:delaiServiceSec) {
        Dire "$Nom : pret (127.0.0.1:$Port)."
        return $true
    }
    Dire "$Nom : pas de reponse apres $($script:delaiServiceSec) s."
    Ajouter-Manque "$Nom ne repond pas sur le port $Port. Verifiez les modeles et docker logs mother-core-dev."
    return $false
}

function Demarrer-HostAgent {
    if (Port-Repond -Port 8001) {
        Dire 'Host-agent : deja en service (127.0.0.1:8001).'
        return $true
    }
    Dire 'Host-agent : demarrage dans mother-core-dev.'
    & docker exec -d mother-core-dev bash /workspace/dev/scripts/relance_hostagent.sh | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Dire 'Host-agent : commande de demarrage refusee.'
        Ajouter-Manque 'Le host-agent ne demarre pas. Consultez docker logs mother-core-dev.'
        return $false
    }
    if (Attendre -Condition { Port-Repond -Port 8001 } -Secondes $script:delaiServiceSec) {
        Dire 'Host-agent : pret (127.0.0.1:8001).'
        return $true
    }
    Dire "Host-agent : pas de reponse apres $($script:delaiServiceSec) s."
    Ajouter-Manque 'Le host-agent ne repond pas sur le port 8001. Consultez docker logs mother-core-dev.'
    return $false
}

function Demarrer-Presence {
    param([object[]]$Existants = @())
    $existants = @($Existants)
    if ($existants.Count -eq 0) { $existants = @(Processus-Presence) }
    if ($existants.Count -gt 0) {
        Dire "Presence : deja en service (PID $($existants[0].ProcessId))."
        return $true
    }
    $scriptPresence = Join-Path $script:racine 'native\presence\hyper-ambient.bat'
    if (-not (Test-Path -LiteralPath $scriptPresence)) {
        Dire 'Presence : lanceur introuvable.'
        Ajouter-Manque 'Presence est introuvable. Executez installer.ps1 -Diagnostic.'
        return $false
    }
    Dire 'Presence : demarrage.'
    Start-Process -FilePath $scriptPresence -WorkingDirectory $script:racine | Out-Null
    if (Attendre -Condition ${function:Processus-Presence} -Secondes 10) {
        Dire 'Presence : prete.'
        return $true
    }
    Dire 'Presence : lancee, mais son processus n''est pas encore visible ; consultez %LOCALAPPDATA%\hyper-ambient\presence.log.'
    Ajouter-Manque 'Presence ne confirme pas son demarrage. Consultez %LOCALAPPDATA%\hyper-ambient\presence.log.'
    return $false
}

try {
    $ici = $PSScriptRoot
    if ([string]::IsNullOrWhiteSpace($ici)) { $ici = Split-Path -Parent $MyInvocation.MyCommand.Path }
    if ([string]::IsNullOrWhiteSpace($ici)) { throw 'emplacement du lanceur introuvable.' }
    $script:racine = (Resolve-Path -LiteralPath (Join-Path $ici '..\..')).Path
    Set-Location -LiteralPath $script:racine
    Dire "hyper-ambient — racine : $($script:racine)"

    # Controler Presence avant tout lancement externe : une instance deja
    # active ne doit jamais etre empilee pendant l'initialisation du reste.
    $presenceAvantLancements = @(Processus-Presence)
    $dockerOk = Demarrer-Docker
    $conteneurOk = $false
    if ($dockerOk) { $conteneurOk = Demarrer-Conteneur }
    if ($conteneurOk) {
        [void](Demarrer-ServeurModele -Nom 'BRAIN local (llama)' -Port 8090 -Script '/workspace/dev/scripts/serve_llama.sh')
        [void](Demarrer-ServeurModele -Nom 'EARS local (whisper)' -Port 8091 -Script '/workspace/dev/scripts/serve_whisper.sh')
        [void](Demarrer-HostAgent)
    }
    $presenceOk = Demarrer-Presence -Existants $presenceAvantLancements

    Dire ''
    Dire 'Etat final :'
    Dire ("  Docker : " + $(if (Docker-Repond) { 'en service' } else { 'indisponible' }))
    Dire ("  mother-core-dev : " + $(if ((Docker-Repond) -and ((Etat-Conteneur) -eq 'running')) { 'en service' } else { 'indisponible' }))
    Dire ("  BRAIN local : " + $(if (Port-Repond -Port 8090) { 'en service, port 8090' } else { 'indisponible, port 8090' }))
    Dire ("  EARS local : " + $(if (Port-Repond -Port 8091) { 'en service, port 8091' } else { 'indisponible, port 8091' }))
    Dire ("  Host-agent : " + $(if (Port-Repond -Port 8001) { 'en service, port 8001' } else { 'indisponible, port 8001' }))
    Dire ("  Presence : " + $(if ($presenceOk) { 'en service' } else { 'indisponible' }))
    if ($script:manques.Count -gt 0) {
        Dire 'A corriger :'
        foreach ($manque in $script:manques) { Dire "  - $manque" }
        exit 1
    }
    Dire 'Pret : ouvrez Presence et utilisez le bouton parler. Si un element manque, executez installer.ps1 -Diagnostic.'
    exit 0
} catch {
    Dire "Echec : $($_.Exception.Message)"
    Dire 'Pour les prealables manquants, executez installer.ps1 -Diagnostic.'
    exit 1
}
