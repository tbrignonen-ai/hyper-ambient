# Amorcage Windows d'hyper-ambient.
# Diagnostique d'abord, installe ce qui est automatisable, nomme le reste.
# Idempotent : chaque etape verifie avant d'agir. Relancer apres un
# redemarrage reprend sans refaire ce qui est deja en place.
# Ne demande jamais une elevation sans dire pourquoi.

[CmdletBinding()]
param(
    [switch]$Diagnostic
)

$ErrorActionPreference = 'Stop'

# Console UTF-8 des le depart : les accents restent lisibles.
# Sans cela, PowerShell 5.1 herite de la page OEM et affiche d?faut.
try {
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [Console]::InputEncoding = $utf8
    [Console]::OutputEncoding = $utf8
    $OutputEncoding = $utf8
} catch {
}
try {
    $chcp = Join-Path $env:SystemRoot 'System32\chcp.com'
    if (Test-Path -LiteralPath $chcp) {
        & $chcp 65001 | Out-Null
    }
} catch {
}

$script:manques = New-Object System.Collections.Generic.List[string]
$script:piloteMinimum = '551.61'
$script:disqueMinimumGo = 40
$script:dockerAttenteSec = 180

function Dire {
    param([string]$Ligne)
    Write-Host $Ligne
}

function Dire-Ligne-Diag {
    param(
        [string]$Etiquette,
        [string]$Texte,
        [string]$Couleur = 'White'
    )
    Write-Host ($Etiquette + $Texte) -ForegroundColor $Couleur
}

function Couleur-Etat {
    param($Ok, $Incertain)
    if ($Ok -and $Incertain) { return 'Yellow' }
    if ($Ok) { return 'Green' }
    return 'Red'
}

function Dire-Etape {
    param([string]$Nom)
    Write-Host ''
    Write-Host "--- $Nom ---"
}

function Echec {
    param([string]$Message)
    Write-Host "Echec : $Message"
    exit 1
}

function Manque {
    param([string]$Texte)
    [void]$script:manques.Add($Texte)
}

function Est-Administrateur {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $prin = New-Object Security.Principal.WindowsPrincipal($id)
    return $prin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Rafraichir-Path {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

function Version-AuMoins {
    param([string]$Actuelle, [string]$Minimum)
    try {
        return ([version]$Actuelle) -ge ([version]$Minimum)
    } catch {
        return $false
    }
}

function Nettoyer-Sortie {
    param($Valeur)
    $texte = ($Valeur | Out-String)
    return ($texte -replace "`0", '').Trim()
}

function Decoder-Sortie-Natif {
    param([byte[]]$Octets)
    if ($null -eq $Octets -or $Octets.Length -eq 0) { return '' }
    $utf16 = $false
    if ($Octets.Length -ge 2 -and $Octets[0] -eq 0xFF -and $Octets[1] -eq 0xFE) {
        $utf16 = $true
    } elseif ($Octets.Length -ge 4) {
        $nuls = 0
        $lim = [Math]::Min($Octets.Length, 40)
        for ($i = 1; $i -lt $lim; $i += 2) {
            if ($Octets[$i] -eq 0) { $nuls++ }
        }
        if ($nuls -ge 8) { $utf16 = $true }
    }
    if ($utf16) {
        $texte = [System.Text.Encoding]::Unicode.GetString($Octets)
    } else {
        $texte = [System.Text.Encoding]::UTF8.GetString($Octets)
    }
    return (($texte -replace "`0", '').Trim())
}

function Appeler-Natif {
    param(
        [string]$Fichier,
        [string]$Arguments
    )
    $vide = [pscustomobject]@{ Code = -1; Texte = '' }
    if (-not $Fichier) { return $vide }
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Fichier
        $psi.Arguments = $Arguments
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $proc = New-Object System.Diagnostics.Process
        $proc.StartInfo = $psi
        [void]$proc.Start()
        $msOut = New-Object System.IO.MemoryStream
        $msErr = New-Object System.IO.MemoryStream
        $tOut = $proc.StandardOutput.BaseStream.CopyToAsync($msOut)
        $tErr = $proc.StandardError.BaseStream.CopyToAsync($msErr)
        if (-not $proc.WaitForExit(20000)) {
            try { $proc.Kill() } catch { }
            return $vide
        }
        [void]$tOut.Wait(2000)
        [void]$tErr.Wait(2000)
        $octets = $msOut.ToArray()
        if ($octets.Length -eq 0) { $octets = $msErr.ToArray() }
        return [pscustomobject]@{
            Code  = [int]$proc.ExitCode
            Texte = (Decoder-Sortie-Natif -Octets $octets)
        }
    } catch {
        return $vide
    }
}

function Lire-Registre64 {
    param(
        [string]$SousCle,
        [string]$Nom
    )
    try {
        $vue = [Microsoft.Win32.RegistryView]::Registry64
        $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine, $vue)
        $cle = $base.OpenSubKey($SousCle)
        if ($null -eq $cle) { return $null }
        if ([string]::IsNullOrEmpty($Nom)) { return $true }
        return $cle.GetValue($Nom)
    } catch {
        return $null
    }
}

function Extraire-Versions-Distro {
    param([string]$Texte)
    $trouvee = New-Object System.Collections.Generic.List[int]
    if ([string]::IsNullOrWhiteSpace($Texte)) { return $trouvee }
    foreach ($ligne in ($Texte -split '\r?\n')) {
        $t = $ligne.Trim()
        if (-not $t) { continue }
        if ($t -match '\s([12])\s*$') {
            [void]$trouvee.Add([int]$Matches[1])
        }
    }
    return $trouvee
}

function Extraire-Numero-Version {
    param([string]$Texte)
    if ([string]::IsNullOrWhiteSpace($Texte)) { return $null }
    if ($Texte -match '(\d+\.\d+(?:\.\d+){0,3})') {
        return $Matches[1]
    }
    return $null
}

function Chemin-Wsl {
    $direct = Join-Path $env:SystemRoot 'System32\wsl.exe'
    $native = Join-Path $env:SystemRoot 'Sysnative\wsl.exe'
    if (Test-Path -LiteralPath $direct) { return $direct }
    if (Test-Path -LiteralPath $native) { return $native }
    $cmd = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    return $null
}

function Chemin-DockerDesktop {
    $candidats = @(
        (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Docker\Docker\Docker Desktop.exe')
    )
    foreach ($c in $candidats) {
        if ($c -and (Test-Path -LiteralPath $c)) { return $c }
    }
    return $null
}

function Chemin-Etat {
    return (Join-Path $env:LOCALAPPDATA 'hyper-ambient\installeur-etat.json')
}

function Charger-Etat {
    $chemin = Chemin-Etat
    if (-not (Test-Path -LiteralPath $chemin)) {
        return [pscustomobject]@{
            wslRedemarrage = $false
            derniereEtape  = ''
        }
    }
    try {
        $obj = Get-Content -LiteralPath $chemin -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -eq $obj.wslRedemarrage) { $obj | Add-Member -NotePropertyName wslRedemarrage -NotePropertyValue $false }
        if ($null -eq $obj.derniereEtape) { $obj | Add-Member -NotePropertyName derniereEtape -NotePropertyValue '' }
        return $obj
    } catch {
        return [pscustomobject]@{
            wslRedemarrage = $false
            derniereEtape  = ''
        }
    }
}

function Sauver-Etat {
    param($Etat)
    $chemin = Chemin-Etat
    $dossier = Split-Path -Parent $chemin
    if (-not (Test-Path -LiteralPath $dossier)) {
        New-Item -ItemType Directory -Path $dossier -Force | Out-Null
    }
    $Etat | ConvertTo-Json | Set-Content -LiteralPath $chemin -Encoding UTF8
}

function Redemarrage-EnAttente {
    $cles = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootRequired',
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
    )
    foreach ($c in $cles) {
        if (Test-Path $c) { return $true }
    }
    try {
        $sm = Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations -ErrorAction SilentlyContinue
        if ($sm -and $sm.PendingFileRenameOperations) { return $true }
    } catch {
    }
    return $false
}

function Libre-Go {
    param([string]$RacineDisque)
    try {
        $id = $RacineDisque.TrimEnd('\').TrimEnd('/')
        if ($id -notmatch ':$') { $id = "$id`:" }
        $vol = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='$id'" -ErrorAction Stop
        if ($null -eq $vol -or $null -eq $vol.FreeSpace) { return $null }
        return [math]::Round(($vol.FreeSpace / 1GB), 1)
    } catch {
        return $null
    }
}

function Trouver-Python {
    Rafraichir-Path
    foreach ($nom in @('python', 'python3', 'py')) {
        $cmd = Get-Command $nom -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -and ($cmd.Source -notmatch 'WindowsApps\\python.exe$')) {
            try {
                $ver = Nettoyer-Sortie (& $cmd.Source --version 2>&1)
                if ($ver -match 'Python\s+\d+') {
                    return [pscustomobject]@{ Ok = $true; Texte = "$ver ($($cmd.Source))" }
                }
            } catch {
            }
        }
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $ver = Nettoyer-Sortie (& $py.Source -3 --version 2>&1)
            if ($ver -match 'Python\s+\d+') {
                return [pscustomobject]@{ Ok = $true; Texte = "$ver (py -3)" }
            }
        } catch {
        }
    }
    return [pscustomobject]@{ Ok = $false; Texte = 'absent' }
}

function Trouver-Virtualisation {
    $firmware = $null
    $hyperviseur = $false
    try {
        $cpu = Get-CimInstance -ClassName Win32_Processor -ErrorAction Stop | Select-Object -First 1
        if ($null -ne $cpu.VirtualizationFirmwareEnabled) {
            $firmware = [bool]$cpu.VirtualizationFirmwareEnabled
        }
    } catch {
    }
    try {
        $cs = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
        $hyperviseur = [bool]$cs.HypervisorPresent
    } catch {
    }
    if ($firmware -eq $true -or $hyperviseur) {
        $detail = 'activee'
        if ($firmware -eq $true) { $detail = 'activee dans le firmware' }
        if ($hyperviseur) { $detail = "$detail ; hyperviseur present" }
        return [pscustomobject]@{ Ok = $true; Incertain = $false; Texte = $detail }
    }
    if ($firmware -eq $false) {
        return [pscustomobject]@{ Ok = $false; Incertain = $false; Texte = 'desactivee dans le firmware (BIOS/UEFI)' }
    }
    return [pscustomobject]@{
        Ok        = $true
        Incertain = $true
        Texte     = 'indeterminee (lecture firmware refusee, je ne bloque pas)'
    }
}

function Trouver-WSL2 {
    $wsl = Chemin-Wsl
    if (-not $wsl) {
        return [pscustomobject]@{ Ok = $false; Incertain = $false; Texte = 'wsl.exe absent' }
    }

    # Jamais de phrases localisees. Signaux : chiffres, codes, registre, services.
    $versionReg = $null
    $vReg = Lire-Registre64 -SousCle 'SOFTWARE\Microsoft\Windows\CurrentVersion\Lxss' -Nom 'DefaultVersion'
    if ($null -ne $vReg) {
        try { $versionReg = [int]$vReg } catch { $versionReg = $null }
    }
    if ($null -eq $versionReg) {
        try {
            $lxss = Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Lxss' -Name DefaultVersion -ErrorAction SilentlyContinue
            if ($lxss) { $versionReg = [int]$lxss.DefaultVersion }
        } catch {
        }
    }

    $liste = Appeler-Natif -Fichier $wsl -Arguments '-l -v'
    $versions = Extraire-Versions-Distro -Texte $liste.Texte
    $aV2 = $false
    $aV1 = $false
    foreach ($v in $versions) {
        if ($v -eq 2) { $aV2 = $true }
        if ($v -eq 1) { $aV1 = $true }
    }

    $verCmd = Appeler-Natif -Fichier $wsl -Arguments '--version'
    $numeroWsl = Extraire-Numero-Version -Texte $verCmd.Texte

    $listeQ = Appeler-Natif -Fichier $wsl -Arguments '-l -q'
    $wslRepond = ($liste.Code -eq 0) -or ($listeQ.Code -eq 0)

    if ($aV2) {
        return [pscustomobject]@{ Ok = $true; Incertain = $false; Texte = 'present (distribution en version 2)' }
    }
    if ($verCmd.Code -eq 0 -and $numeroWsl) {
        return [pscustomobject]@{ Ok = $true; Incertain = $false; Texte = "present (wsl $numeroWsl)" }
    }
    if ($versionReg -eq 2) {
        return [pscustomobject]@{ Ok = $true; Incertain = $false; Texte = 'present (version par defaut 2)' }
    }

    if ($aV1 -and -not $aV2 -and $versionReg -ne 2 -and -not $numeroWsl) {
        return [pscustomobject]@{ Ok = $false; Incertain = $false; Texte = 'present en version 1 seulement (WSL2 requis)' }
    }

    if ($wslRepond) {
        return [pscustomobject]@{
            Ok        = $true
            Incertain = $true
            Texte     = 'wsl.exe repond, version 2 non lue (je ne bloque pas)'
        }
    }

    $composant = $false
    $lectureComposantImpossible = $false
    if ($null -ne (Lire-Registre64 -SousCle 'SOFTWARE\Microsoft\Windows\CurrentVersion\Lxss' -Nom $null)) {
        $composant = $true
    } elseif (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Lxss') {
        $composant = $true
    } else {
        foreach ($nom in @('LxssManager', 'WslService', 'WslInstaller')) {
            if (Get-Service -Name $nom -ErrorAction SilentlyContinue) { $composant = $true; break }
        }
        if (-not $composant) {
            try {
                $feat = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -ErrorAction Stop
                if ($feat) {
                    $etat = $feat.State.ToString()
                    if ($etat -eq 'Enabled' -or $etat -eq 'EnablePending') { $composant = $true }
                }
            } catch {
                $lectureComposantImpossible = $true
            }
        }
    }

    if ($composant) {
        return [pscustomobject]@{
            Ok        = $true
            Incertain = $true
            Texte     = 'wsl.exe repond, version 2 non lue (je ne bloque pas)'
        }
    }

    if ($lectureComposantImpossible) {
        return [pscustomobject]@{
            Ok        = $true
            Incertain = $true
            Texte     = 'wsl.exe present, WSL2 non confirme (je ne bloque pas)'
        }
    }

    return [pscustomobject]@{
        Ok        = $false
        Incertain = $false
        Texte     = 'wsl.exe present, composant Windows pas encore installe'
    }
}

function Docker-Repond {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) { return $false }
    try {
        $null = & docker info 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Trouver-Docker {
    Rafraichir-Path
    $exe = Chemin-DockerDesktop
    $cmd = Get-Command docker -ErrorAction SilentlyContinue
    $installe = [bool]($exe -or $cmd)
    $processus = Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue
    $repond = $false
    if ($cmd) { $repond = Docker-Repond }
    $texte = 'absent'
    if ($installe -and $repond) {
        $ver = ''
        try { $ver = Nettoyer-Sortie ((& docker version --format '{{.Server.Version}}') 2>&1) } catch { }
        if ($ver) { $texte = "installe, demarre, repond ($ver)" }
        else { $texte = 'installe, demarre, repond' }
    } elseif ($installe -and $processus) {
        $texte = 'installe et lance, mais le moteur ne repond pas encore (licence Docker au premier lancement ?)'
    } elseif ($installe) {
        $texte = 'installe, arrete'
    }
    return [pscustomobject]@{
        Ok        = $repond
        Installe  = $installe
        Demarre   = [bool]$processus
        Texte     = $texte
        Exe       = $exe
    }
}

function Trouver-Nvidia {
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($smi) {
        try {
            $csv = Nettoyer-Sortie ((& nvidia-smi --query-gpu=name,driver_version --format=csv,noheader) 2>&1)
            $ligne = ($csv -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 1)
            if ($ligne -match ',') {
                $parts = $ligne.Split(',')
                $nom = $parts[0].Trim()
                $pilote = $parts[1].Trim()
                $ok = Version-AuMoins -Actuelle $pilote -Minimum $script:piloteMinimum
                $texte = "$nom, pilote $pilote"
                if (-not $ok) {
                    $texte = "$texte (trop ancien, minimum $($script:piloteMinimum) pour CUDA 12.4)"
                }
                return [pscustomobject]@{ Ok = $ok; Incertain = $false; Present = $true; Texte = $texte; Pilote = $pilote }
            }
        } catch {
        }
    }
    $cimOk = $false
    try {
        $cartes = Get-CimInstance -ClassName Win32_VideoController -ErrorAction Stop |
            Where-Object { $_.Name -match 'NVIDIA' }
        $cimOk = $true
        if ($cartes) {
            $nom = ($cartes | Select-Object -First 1).Name
            return [pscustomobject]@{
                Ok        = $false
                Incertain = $false
                Present   = $true
                Texte     = "$nom detectee, nvidia-smi absent (pilote incomplet)"
                Pilote    = ''
            }
        }
    } catch {
        $cimOk = $false
    }
    if (-not $cimOk) {
        if ($smi) {
            return [pscustomobject]@{
                Ok        = $true
                Incertain = $true
                Present   = $true
                Texte     = 'nvidia-smi present, details illisibles (je ne bloque pas)'
                Pilote    = ''
            }
        }
        return [pscustomobject]@{
            Ok        = $true
            Incertain = $true
            Present   = $false
            Texte     = 'inventaire GPU illisible (je ne bloque pas)'
            Pilote    = ''
        }
    }
    return [pscustomobject]@{
        Ok        = $false
        Incertain = $false
        Present   = $false
        Texte     = 'aucune GPU NVIDIA detectee'
        Pilote    = ''
    }
}

function Trouver-Conteneur {
    $cmd = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $cmd) {
        return [pscustomobject]@{ Ok = $false; Texte = 'docker absent, conteneur non verifiable' }
    }
    if (-not (Docker-Repond)) {
        return [pscustomobject]@{ Ok = $false; Texte = 'moteur Docker muet, conteneur non verifiable' }
    }
    try {
        $etat = Nettoyer-Sortie ((& docker inspect -f '{{.State.Status}}' mother-core-dev) 2>&1)
        if ($LASTEXITCODE -eq 0 -and $etat -eq 'running') {
            return [pscustomobject]@{ Ok = $true; Texte = 'mother-core-dev en marche' }
        }
        if ($LASTEXITCODE -eq 0 -and $etat) {
            return [pscustomobject]@{ Ok = $false; Texte = "mother-core-dev existe, etat : $etat" }
        }
    } catch {
    }
    return [pscustomobject]@{ Ok = $false; Texte = 'mother-core-dev absent' }
}

function Image-Locale-Presente {
    try {
        $null = & docker image inspect mother-core:latest 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Trouver-Raccourcis {
    $bureau = [Environment]::GetFolderPath('Desktop')
    $programmes = [Environment]::GetFolderPath('Programs')
    $lnkBureau = Join-Path $bureau 'hyper-ambient.lnk'
    $lnkMenu = Join-Path $programmes 'hyper-ambient.lnk'
    $b = Test-Path -LiteralPath $lnkBureau
    $m = Test-Path -LiteralPath $lnkMenu
    if ($b -and $m) {
        return [pscustomobject]@{ Ok = $true; Texte = 'poses (bureau et menu Demarrer)' }
    }
    if ($b -or $m) {
        return [pscustomobject]@{ Ok = $false; Texte = 'partiels (un seul emplacement)' }
    }
    return [pscustomobject]@{ Ok = $false; Texte = 'absents' }
}

function Dire-Limites {
    Dire-Etape 'Ce que ce script ne peut pas faire'
    Dire "Virtualisation BIOS : aucun programme ne peut l'activer, c'est du firmware. Redemarrez, entrez dans le BIOS/UEFI (souvent Del, F2, F10 ou Esc selon le PC), cherchez Intel VT-x / Intel Virtualization Technology, ou AMD-V / SVM, activez, enregistrez, repartez."
    Dire "Redemarrage WSL2 : apres wsl --install, Windows doit redemarrer. Relancez ensuite exactement la meme commande ; le script reprend ou il en etait, sans refaire les etapes deja faites."
    Dire "Licence Docker Desktop : au premier lancement, une fenetre Docker demande d'accepter la licence. Aucun script ne peut cliquer pour vous. Acceptez, puis relancez."
    Dire "Pilote NVIDIA trop ancien : ce script ne le met pas a jour. CUDA 12.4 exige au minimum le pilote $($script:piloteMinimum). Telechargez-le ici : https://www.nvidia.com/Download/index.aspx"
}

function Lancer-Eleve {
    param(
        [string]$Fichier,
        [string]$Arguments,
        [string]$Pourquoi
    )
    Dire "Droits administrateur : $Pourquoi"
    if (Est-Administrateur) {
        $p = Start-Process -FilePath $Fichier -ArgumentList $Arguments -Wait -PassThru -NoNewWindow
        return $p.ExitCode
    }
    Dire "Windows va afficher une demande d'elevation. Refusez-la et cette etape s'arrete, sans trace obscure."
    try {
        $p = Start-Process -FilePath $Fichier -ArgumentList $Arguments -Wait -PassThru -Verb RunAs
        if ($null -eq $p) { return 1 }
        return $p.ExitCode
    } catch {
        throw "elevation refusee ou impossible ($($_.Exception.Message)). Relancez et acceptez, ou faites l'installation a la main."
    }
}

function Trouver-Winget {
    Rafraichir-Path
    $cmd = Get-Command winget -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    $store = Join-Path $env:LocalAppData 'Microsoft\WindowsApps\winget.exe'
    if (Test-Path -LiteralPath $store) { return $store }
    return $null
}

function Attendre-Docker {
    param([int]$Secondes)
    $limite = (Get-Date).AddSeconds($Secondes)
    $prochainMessage = (Get-Date)
    while ((Get-Date) -lt $limite) {
        Rafraichir-Path
        if (Docker-Repond) { return $true }
        if ((Get-Date) -ge $prochainMessage) {
            $reste = [int]($limite - (Get-Date)).TotalSeconds
            Dire "Docker ne repond pas encore, j'attends (encore ~$reste s, delai borne $($Secondes)s)."
            $prochainMessage = (Get-Date).AddSeconds(15)
        }
        Start-Sleep -Seconds 5
    }
    return $false
}

function Diagnostiquer {
    param(
        [string]$Racine,
        [string]$Titre = 'Diagnostic (rien ne change pendant cette etape)'
    )

    Dire-Etape $Titre

    $os = $null
    try { $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop } catch { }
    $windowsTexte = 'inconnu (lecture OS refusee, je ne bloque pas)'
    $windowsOk = $true
    $windowsIncertain = $true
    $build = 0
    if ($os) {
        $build = [int]$os.BuildNumber
        $windowsTexte = "$($os.Caption) $($os.Version) (build $build)"
        $windowsOk = ($build -ge 19041)
        $windowsIncertain = $false
        if (-not $windowsOk) {
            $windowsTexte = "$windowsTexte - trop ancien pour WSL2 (build 19041 requis)"
        }
    }

    $virt = Trouver-Virtualisation
    $wsl = Trouver-WSL2
    $docker = Trouver-Docker
    $gpu = Trouver-Nvidia
    $python = Trouver-Python
    $conteneur = Trouver-Conteneur
    $raccourcis = Trouver-Raccourcis

    $repoRoot = [System.IO.Path]::GetPathRoot($Racine)
    $sysRoot = [System.IO.Path]::GetPathRoot($env:SystemRoot)
    $libreRepo = Libre-Go $repoRoot
    $libreSys = Libre-Go $sysRoot
    $disqueTexte = "depot $repoRoot "
    if ($null -ne $libreRepo) { $disqueTexte += "$libreRepo Go libres" } else { $disqueTexte += 'lecture impossible' }
    $disqueTexte += " ; systeme $sysRoot "
    if ($null -ne $libreSys) { $disqueTexte += "$libreSys Go libres" } else { $disqueTexte += 'lecture impossible' }
    $disqueOk = $true
    if ($null -ne $libreRepo -and $libreRepo -lt $script:disqueMinimumGo -and -not $conteneur.Ok) {
        $disqueOk = $false
        $disqueTexte += " (moins de $($script:disqueMinimumGo) Go sur le depot : l'image fait ~32 Go)"
    }
    if ($null -ne $libreSys -and $libreSys -lt $script:disqueMinimumGo -and -not $conteneur.Ok) {
        $disqueOk = $false
        $disqueTexte += " (moins de $($script:disqueMinimumGo) Go sur C: : Docker y stocke les images)"
    }

    Dire "Racine du depot : $Racine"
    Dire-Ligne-Diag 'Windows          : ' $windowsTexte (Couleur-Etat $windowsOk $windowsIncertain)
    Dire-Ligne-Diag 'Virtualisation   : ' $virt.Texte (Couleur-Etat $virt.Ok $virt.Incertain)
    Dire-Ligne-Diag 'WSL2             : ' $wsl.Texte (Couleur-Etat $wsl.Ok $wsl.Incertain)
    Dire-Ligne-Diag 'Docker           : ' $docker.Texte (Couleur-Etat $docker.Ok $false)
    Dire-Ligne-Diag 'GPU NVIDIA       : ' $gpu.Texte (Couleur-Etat $gpu.Ok $gpu.Incertain)
    Dire-Ligne-Diag 'Python           : ' $python.Texte (Couleur-Etat $python.Ok $false)
    Dire-Ligne-Diag 'Conteneur        : ' $conteneur.Texte (Couleur-Etat $conteneur.Ok $false)
    Dire-Ligne-Diag 'Raccourcis       : ' $raccourcis.Texte (Couleur-Etat $raccourcis.Ok $false)
    Dire-Ligne-Diag 'Disque           : ' $disqueTexte (Couleur-Etat $disqueOk $false)
    if (Est-Administrateur) {
        Dire 'Session          : administrateur (deja elevee)'
    } else {
        Dire 'Session          : utilisateur standard (une elevation ne sera demandee que si une etape le justifie)'
    }

    return [pscustomobject]@{
        WindowsOk   = $windowsOk
        Windows     = $windowsTexte
        Virt        = $virt
        Wsl         = $wsl
        Docker      = $docker
        Gpu         = $gpu
        Python      = $python
        Conteneur   = $conteneur
        Raccourcis  = $raccourcis
        DisqueOk    = $disqueOk
        Disque      = $disqueTexte
    }
}

function Manques-Depuis-Diagnostic {
    param($Diag)
    if (-not $Diag.WindowsOk) {
        Manque "Windows trop ancien pour WSL2 : $($Diag.Windows). Passez a Windows 10 2004+ ou Windows 11."
    }
    if (-not $Diag.Virt.Ok) {
        Manque "virtualisation desactivee ou illisible. Redemarrez, entrez dans le BIOS/UEFI (Del, F2, F10 ou Esc), activez Intel VT-x / Intel Virtualization Technology, ou AMD-V / SVM, enregistrez."
    }
    if (-not $Diag.Wsl.Ok) {
        Manque "WSL2 absent ou incomplet ($($Diag.Wsl.Texte))."
    }
    if (-not $Diag.Docker.Installe) {
        Manque 'Docker Desktop n''est pas installe.'
    } elseif (-not $Diag.Docker.Ok) {
        Manque "Docker Desktop ne repond pas ($($Diag.Docker.Texte)). Au premier lancement, acceptez la licence dans la fenetre Docker, puis relancez ce script."
    }
    if (-not $Diag.Gpu.Ok) {
        if (-not $Diag.Gpu.Present) {
            Manque 'aucune GPU NVIDIA. Le coeur exige une carte NVIDIA (RTX 4070 ou equivalent, 12 Go VRAM).'
        } else {
            Manque "pilote NVIDIA trop ancien ou incomplet ($($Diag.Gpu.Texte)). Telechargez un pilote >= $($script:piloteMinimum) : https://www.nvidia.com/Download/index.aspx - ce script ne l'installera pas."
        }
    }
    if (-not $Diag.Python.Ok) {
        Manque 'Python absent (le lanceur hyper-ambient.bat appelle pythonw sur l''hote).'
    }
    if (-not $Diag.Conteneur.Ok) {
        Manque "conteneur mother-core-dev pas en marche ($($Diag.Conteneur.Texte))."
    }
    if (-not $Diag.Raccourcis.Ok) {
        Manque "raccourcis Windows absents ou partiels ($($Diag.Raccourcis.Texte))."
    }
    if (-not $Diag.DisqueOk) {
        Manque "place disque insuffisante ($($Diag.Disque)). Liberer de l'espace, puis relancer."
    }
}

function Installer-Python {
    param($Diag)
    Dire-Etape 'Python'
    if ($Diag.Python.Ok) {
        Dire "Deja present : $($Diag.Python.Texte). Rien a installer."
        return
    }
    $winget = Trouver-Winget
    if (-not $winget) {
        Manque 'Python absent, et winget aussi. Installez Python 3.13 depuis https://www.python.org/downloads/ (cochez Add python.exe to PATH), puis relancez.'
        Dire 'winget est absent : je ne peux pas proposer Python.Python.3.13.'
        return
    }
    Dire 'Python absent : j''installe Python.Python.3.13 via winget (portee utilisateur, sans elevation).'
    $argsUser = 'install --id Python.Python.3.13 -e --source winget --scope user --accept-package-agreements --accept-source-agreements --disable-interactivity'
    $code = 1
    try {
        $p = Start-Process -FilePath $winget -ArgumentList $argsUser -Wait -PassThru -NoNewWindow
        $code = $p.ExitCode
    } catch {
        $code = 1
    }
    if ($code -ne 0) {
        Dire "L'install utilisateur a echoue (code $code). Je retente au niveau machine : winget doit ecrire dans Program Files."
        try {
            $code = Lancer-Eleve -Fichier $winget -Arguments $argsUser.Replace('--scope user ', '') -Pourquoi 'installer Python pour tous les comptes de cette machine (ecriture dans Program Files).'
        } catch {
            Dire $_.Exception.Message
            Manque 'Python : installation refusee ou echouee. Relancez et acceptez l''elevation, ou installez Python.Python.3.13 a la main via winget.'
            return
        }
    }
    Rafraichir-Path
    $apres = Trouver-Python
    if ($apres.Ok) {
        Dire "Python installe : $($apres.Texte)."
        $Diag.Python = $apres
    } else {
        Dire 'Python a ete installe mais ce terminal ne le voit pas encore. Fermez ce PowerShell, ouvrez-en un nouveau, relancez le script.'
        Manque 'Python installe, PATH pas encore rafraichi. Ouvrez un nouveau PowerShell et relancez ce script.'
    }
}

function Installer-WSL2 {
    param($Diag, $Etat)
    Dire-Etape 'WSL2'
    if ($Diag.Wsl.Ok) {
        Dire "Deja present : $($Diag.Wsl.Texte). Rien a installer."
        if ($Etat.wslRedemarrage) {
            $Etat.wslRedemarrage = $false
            $Etat.derniereEtape = 'wsl'
            Sauver-Etat $Etat
        }
        return $false
    }
    if (-not $Diag.Virt.Ok) {
        Dire 'Virtualisation inactive ou illisible : je n''appelle pas wsl --install, ca echouerait.'
        return $false
    }
    $wsl = Chemin-Wsl
    if (-not $wsl) {
        $wsl = Join-Path $env:SystemRoot 'System32\wsl.exe'
    }
    Dire 'WSL2 absent : j''execute wsl --install --no-distribution (active le composant, sans Ubuntu : Docker Desktop apporte ses propres distros ; un Ubuntu demanderait un compte interactif que je ne peux pas remplir).'
    $code = 1
    try {
        $code = Lancer-Eleve -Fichier $wsl -Arguments '--install --no-distribution' -Pourquoi 'activer le composant Windows Subsystem for Linux et la plateforme de machine virtuelle.'
    } catch {
        Dire $_.Exception.Message
        Manque 'WSL2 : elevation refusee ou wsl --install impossible. Relancez en acceptant la demande, ou ouvrez PowerShell administrateur et tapez : wsl --install --no-distribution'
        return $false
    }
    Start-Sleep -Seconds 2
    $apres = Trouver-WSL2
    $Diag.Wsl = $apres
    if ($apres.Ok -and -not (Redemarrage-EnAttente)) {
        Dire "WSL2 est pret sans redemarrage : $($apres.Texte)."
        $Etat.wslRedemarrage = $false
        $Etat.derniereEtape = 'wsl'
        Sauver-Etat $Etat
        return $false
    }
    $Etat.wslRedemarrage = $true
    $Etat.derniereEtape = 'wsl-reboot'
    Sauver-Etat $Etat
    Dire 'Redemarrage requis. Windows doit redemarrer pour finir WSL2. Relancez ensuite la meme commande : le script reprendra ici.'
    Manque 'redemarrage Windows requis pour finir WSL2. Redemarrez, puis relancez : powershell -NoProfile -ExecutionPolicy Bypass -File "packaging\windows\installer.ps1"'
    return $true
}

function Installer-DockerDesktop {
    param($Diag)
    Dire-Etape 'Docker Desktop'
    if ($Diag.Docker.Installe) {
        Dire "Deja installe : $($Diag.Docker.Texte). Je n'installe pas une seconde copie."
        return
    }
    if (-not $Diag.Wsl.Ok) {
        Dire 'WSL2 n''est pas pret : j''attends avant d''installer Docker Desktop.'
        return
    }
    $winget = Trouver-Winget
    if (-not $winget) {
        Manque 'Docker Desktop absent, et winget aussi. Installez Docker Desktop depuis https://www.docker.com/products/docker-desktop/ puis relancez.'
        Dire 'winget est absent : je ne peux pas installer Docker.DockerDesktop.'
        return
    }
    Dire 'Docker Desktop absent : j''installe Docker.DockerDesktop via winget.'
    $arguments = 'install --id Docker.DockerDesktop -e --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity'
    $code = 1
    try {
        $code = Lancer-Eleve -Fichier $winget -Arguments $arguments -Pourquoi 'installer Docker Desktop au niveau machine (services Windows, pilote WSL, raccourci).'
    } catch {
        Dire $_.Exception.Message
        Manque 'Docker Desktop : elevation refusee ou winget en echec. Relancez et acceptez, ou installez a la main : winget install Docker.DockerDesktop'
        return
    }
    Rafraichir-Path
    $apres = Trouver-Docker
    $Diag.Docker = $apres
    if ($apres.Installe) {
        Dire "Docker Desktop installe : $($apres.Texte)."
    } else {
        Dire "winget a rendu le code $code, Docker Desktop n'est pas visible. Relancez apres un eventuel redemarrage demande par l'installateur."
        Manque 'Docker Desktop : installation non visible. S''il a demande un redemarrage, redemarrez puis relancez ce script. Sinon : winget install Docker.DockerDesktop'
    }
}

function Demarrer-Docker {
    param($Diag)
    Dire-Etape 'Demarrage Docker'
    $Diag.Docker = Trouver-Docker
    if (-not $Diag.Docker.Installe) {
        Dire 'Docker Desktop n''est pas installe : rien a demarrer.'
        return
    }
    if ($Diag.Docker.Ok) {
        Dire 'Docker repond deja. Rien a demarrer.'
        return
    }
    $exe = $Diag.Docker.Exe
    if (-not $exe) { $exe = Chemin-DockerDesktop }
    if (-not $exe) {
        Dire 'Executables Docker Desktop introuvables, je ne peux pas le lancer.'
        Manque 'Docker Desktop installe mais son lanceur est introuvable. Ouvrez Docker Desktop depuis le menu Demarrer, acceptez la licence, puis relancez.'
        return
    }
    Dire "Docker est arrete : je lance `"$exe`" et j'attends qu'il reponde (au plus $($script:dockerAttenteSec) s)."
    try {
        Start-Process -FilePath $exe | Out-Null
    } catch {
        Dire "Lancement refuse : $($_.Exception.Message)"
        Manque 'Docker Desktop n''a pas pu etre lance. Ouvrez-le a la main, acceptez la licence au premier lancement, puis relancez.'
        return
    }
    if (Attendre-Docker -Secondes $script:dockerAttenteSec) {
        $Diag.Docker = Trouver-Docker
        Dire "Docker repond : $($Diag.Docker.Texte)."
        return
    }
    Dire "Delai ecoule ($($script:dockerAttenteSec) s) : Docker n'a pas repondu. Au premier lancement, acceptez la licence dans la fenetre Docker, cochez l'engine WSL2 si on vous le demande, puis relancez ce script."
    Manque "Docker Desktop ne repond pas apres $($script:dockerAttenteSec) s. Acceptez la licence dans sa fenetre (aucun script ne peut le faire), attendez le moteur, relancez."
}

function Preparer-Compose {
    param([string]$Racine)
    foreach ($nom in @('models', 'data', 'logs')) {
        $d = Join-Path $Racine $nom
        if (-not (Test-Path -LiteralPath $d)) {
            New-Item -ItemType Directory -Path $d | Out-Null
            Dire "Dossier cree : $d"
        }
    }
    $envLocal = Join-Path $Racine '.env.local'
    if (-not (Test-Path -LiteralPath $envLocal)) {
        $exemple = Join-Path $Racine '.env.example'
        if (Test-Path -LiteralPath $exemple) {
            Copy-Item -LiteralPath $exemple -Destination $envLocal
            Dire "Fichier .env.local cree depuis .env.example (cles vides : a remplir plus tard, pas par ce script)."
        } else {
            Set-Content -LiteralPath $envLocal -Value '' -Encoding UTF8
            Dire 'Fichier .env.local vide cree (docker compose le monte ; sans lui le demarrage echoue).'
        }
    }
}

function Demarrer-Conteneur {
    param($Diag, [string]$Racine)
    Dire-Etape 'Conteneur mother-core-dev'
    $Diag.Conteneur = Trouver-Conteneur
    $Diag.Docker = Trouver-Docker
    if ($Diag.Conteneur.Ok) {
        Dire 'mother-core-dev tourne deja : je ne le recree pas.'
        return
    }
    if (-not $Diag.Docker.Ok) {
        Dire 'Docker ne repond pas : je ne lance pas docker compose.'
        return
    }
    if (-not $Diag.DisqueOk) {
        Dire "Place disque insuffisante : je n'enclenche pas une construction de ~32 Go."
        return
    }
    $compose = Join-Path $Racine 'docker-compose.yml'
    if (-not (Test-Path -LiteralPath $compose)) {
        Manque "docker-compose.yml introuvable dans $Racine. Ce script doit rester dans packaging\windows\ du depot clone."
        Dire 'Fichier compose introuvable, je m''arrete.'
        return
    }
    Preparer-Compose -Racine $Racine
    Set-Location -LiteralPath $Racine
    if (-not (Image-Locale-Presente)) {
        Dire 'Image mother-core:latest absente : construction (souvent 20 a 40 minutes, ~32 Go). Je ne coupe pas.'
        & docker compose -f $compose build
        if ($LASTEXITCODE -ne 0) {
            Manque "docker compose build a echoue (code $LASTEXITCODE). Relancez ce script une fois la cause corrigee ; il ne reconstruira que si l'image manque encore."
            Dire "Construction echouee (code $LASTEXITCODE)."
            return
        }
        Dire 'Image mother-core:latest construite.'
    } else {
        Dire 'Image mother-core:latest deja presente : je ne reconstruis pas.'
    }
    Dire 'Demarrage du conteneur : docker compose up -d.'
    & docker compose -f $compose up -d
    if ($LASTEXITCODE -ne 0) {
        Manque "docker compose up a echoue (code $LASTEXITCODE). Cause frequente : reservation GPU NVIDIA refusee, ou licence Docker pas encore acceptee. Corrigez, relancez."
        Dire "Demarrage compose echoue (code $LASTEXITCODE)."
        return
    }
    $apres = Trouver-Conteneur
    $Diag.Conteneur = $apres
    if ($apres.Ok) {
        Dire 'Conteneur mother-core-dev en marche.'
    } else {
        Dire "Compose a rendu 0 mais le conteneur n'est pas en marche : $($apres.Texte)."
        Manque "mother-core-dev n'est pas en marche apres compose up ($($apres.Texte))."
    }
}

function Poser-Raccourcis {
    param($Diag, [string]$Ici)
    Dire-Etape 'Raccourcis'
    $scriptRacc = Join-Path $Ici 'installer_raccourcis.ps1'
    if (-not (Test-Path -LiteralPath $scriptRacc)) {
        Manque "installer_raccourcis.ps1 introuvable : $scriptRacc"
        Dire 'Script des raccourcis introuvable, je ne duplique pas sa logique ici.'
        return
    }
    $ps = (Get-Command powershell.exe).Source
    Dire "Appel de `"$scriptRacc`" (aucun code de raccourci duplique ici)."
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptRacc`""
    $p = Start-Process -FilePath $ps -ArgumentList $arguments -Wait -PassThru -NoNewWindow
    $Diag.Raccourcis = Trouver-Raccourcis
    if ($p.ExitCode -eq 0 -and $Diag.Raccourcis.Ok) {
        Dire "Raccourcis en place : $($Diag.Raccourcis.Texte)."
        return
    }
    Dire "Pose des raccourcis incomplete (code $($p.ExitCode), etat : $($Diag.Raccourcis.Texte))."
    Manque "raccourcis : installer_raccourcis.ps1 a rendu $($p.ExitCode). Relancez-le seul, ou relancez cet installateur."
}

function Dire-Verdict {
    param([bool]$ModeDiagnostic)
    Write-Host ''
    if ($script:manques.Count -eq 0) {
        Dire 'Verdict : pret. Python, WSL2, Docker, mother-core-dev et les raccourcis sont en place.'
        Dire 'Ensuite (pas ce script) : modeles dans le conteneur (make models / make models-brain), cles dans .env.local, puis le raccourci hyper-ambient.'
        if ($ModeDiagnostic) {
            Dire 'Mode diagnostic : rien n''a ete installe ni demarre.'
        }
        exit 0
    }
    Dire 'Verdict : pas pret. Il reste :'
    $i = 1
    foreach ($m in $script:manques) {
        Dire "  $i. $m"
        $i++
    }
    if ($ModeDiagnostic) {
        Dire 'Mode diagnostic : rien n''a ete installe ni demarre. Relancez sans -Diagnostic pour agir.'
    } else {
        Dire 'Relancez ce script quand un point ci-dessus est regle : il est idempotent.'
    }
    exit 1
}

# --- main -----------------------------------------------------------------

try {
    $ici = $PSScriptRoot
    if ([string]::IsNullOrWhiteSpace($ici)) {
        $ici = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    if ([string]::IsNullOrWhiteSpace($ici)) {
        throw 'emplacement du script introuvable (ni $PSScriptRoot ni MyInvocation).'
    }

    $racine = (Resolve-Path -LiteralPath (Join-Path $ici '..\..')).Path
    Set-Location -LiteralPath $racine

    $etat = Charger-Etat
    if ($etat.wslRedemarrage) {
        Dire "Reprise : WSL2 etait en cours d'installation avant un redemarrage. On continue la ou c'etait."
    } elseif ($etat.derniereEtape) {
        Dire "Reprise : derniere etape enregistree = $($etat.derniereEtape)."
    }

    $diag = Diagnostiquer -Racine $racine
    Dire-Limites

    if ($Diagnostic) {
        Manques-Depuis-Diagnostic -Diag $diag
        Dire-Verdict -ModeDiagnostic $true
    }

    Dire-Etape 'Actions'
    Dire 'Le diagnostic ci-dessus est l''etat avant toute modification.'

    Installer-Python -Diag $diag

    $stopReboot = Installer-WSL2 -Diag $diag -Etat $etat
    if ($stopReboot) {
        Dire-Verdict -ModeDiagnostic $false
    }

    $diag.Wsl = Trouver-WSL2
    Installer-DockerDesktop -Diag $diag
    Demarrer-Docker -Diag $diag
    Demarrer-Conteneur -Diag $diag -Racine $racine
    Poser-Raccourcis -Diag $diag -Ici $ici

    $etat.derniereEtape = 'fin'
    $etat.wslRedemarrage = $false
    Sauver-Etat $etat

    $diag = Diagnostiquer -Racine $racine -Titre 'Etat apres actions'
    $script:manques.Clear()
    Manques-Depuis-Diagnostic -Diag $diag
    Dire-Verdict -ModeDiagnostic $false
} catch {
    Echec $_.Exception.Message
}
