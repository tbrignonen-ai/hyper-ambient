# Pose ou retire les raccourcis Windows d'hyper-ambient.
# Bureau + menu Demarrer de l'utilisateur. Aucun droit administrateur.
# Relancer deux fois ecrase le meme .lnk : pas de doublon.

[CmdletBinding()]
param(
    [switch]$Supprimer
)

$ErrorActionPreference = 'Stop'

function Dire {
    param([string]$Ligne)
    Write-Host $Ligne
}

function Echec {
    param([string]$Message)
    Write-Host "Echec : $Message"
    exit 1
}

function Icone-Raccourci {
    param([string]$Racine)
    $assets = Join-Path $Racine 'native\presence\assets'
    $officielle = Join-Path $assets 'hyper-ambient.ico'
    if (Test-Path -LiteralPath $officielle) {
        return $officielle
    }
    if (Test-Path -LiteralPath $assets) {
        $autre = Get-ChildItem -LiteralPath $assets -Filter '*.ico' -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($autre) {
            return $autre.FullName
        }
    }
    foreach ($nom in @('pythonw.exe', 'python.exe')) {
        $cmd = Get-Command $nom -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source) {
            return "$($cmd.Source),0"
        }
    }
    return $null
}

function Poser-Raccourci {
    param(
        [string]$CheminLnk,
        [string]$Cible,
        [string]$Arguments,
        [string]$Travail,
        [string]$Icone
    )
    $shell = New-Object -ComObject WScript.Shell
    $raccourci = $shell.CreateShortcut($CheminLnk)
    $raccourci.TargetPath = $Cible
    $raccourci.Arguments = $Arguments
    $raccourci.WorkingDirectory = $Travail
    if ($Icone) {
        $raccourci.IconLocation = $Icone
    }
    $raccourci.Description = 'hyper-ambient'
    $raccourci.Save()
}

function Retirer-Raccourci {
    param([string]$CheminLnk)
    if (Test-Path -LiteralPath $CheminLnk) {
        Remove-Item -LiteralPath $CheminLnk -Force
        return 'retire'
    }
    return 'deja absent'
}

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
    Dire "Racine du depot : $racine"

    $lanceur = Join-Path $ici 'lancer.ps1'
    $powershell = (Get-Command powershell.exe -ErrorAction Stop).Source
    $bureau = [Environment]::GetFolderPath('Desktop')
    $programmes = [Environment]::GetFolderPath('Programs')
    if ([string]::IsNullOrWhiteSpace($bureau)) {
        throw 'dossier Bureau utilisateur introuvable.'
    }
    if ([string]::IsNullOrWhiteSpace($programmes)) {
        throw 'dossier Programmes utilisateur introuvable.'
    }

    $lnkBureau = Join-Path $bureau 'hyper-ambient.lnk'
    $lnkMenu = Join-Path $programmes 'hyper-ambient.lnk'

    if ($Supprimer) {
        $etatBureau = Retirer-Raccourci -CheminLnk $lnkBureau
        Dire "Bureau : raccourci $etatBureau ($lnkBureau)"
        $etatMenu = Retirer-Raccourci -CheminLnk $lnkMenu
        Dire "Menu Demarrer : raccourci $etatMenu ($lnkMenu)"
        Dire 'Termine. Les raccourcis ne sont plus poses.'
        exit 0
    }

    if (-not (Test-Path -LiteralPath $lanceur)) {
        throw "lanceur introuvable : $lanceur. Ce script doit rester dans packaging\windows\ du depot."
    }
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$lanceur`""
    Dire "Cible : $powershell $arguments"
    Dire "Repertoire de travail : $racine"

    if (-not (Test-Path -LiteralPath $programmes)) {
        New-Item -ItemType Directory -Path $programmes | Out-Null
        Dire "Dossier Programmes cree : $programmes"
    }

    $icone = Icone-Raccourci -Racine $racine
    if ($icone) {
        Dire "Icone : $icone"
    } else {
        Dire "Icone : aucune (ni assets, ni python dans le PATH) ; Windows prendra l'icone du .bat"
    }

    $existaitBureau = Test-Path -LiteralPath $lnkBureau
    Poser-Raccourci -CheminLnk $lnkBureau -Cible $powershell -Arguments $arguments -Travail $racine -Icone $icone
    if ($existaitBureau) {
        Dire "Bureau : raccourci mis a jour ($lnkBureau)"
    } else {
        Dire "Bureau : raccourci cree ($lnkBureau)"
    }

    $existaitMenu = Test-Path -LiteralPath $lnkMenu
    Poser-Raccourci -CheminLnk $lnkMenu -Cible $powershell -Arguments $arguments -Travail $racine -Icone $icone
    if ($existaitMenu) {
        Dire "Menu Demarrer : raccourci mis a jour ($lnkMenu)"
    } else {
        Dire "Menu Demarrer : raccourci cree ($lnkMenu)"
    }

    Dire 'Termine. Relancer ce script ecrase les memes fichiers, sans doublon.'
    exit 0
} catch {
    Echec $_.Exception.Message
}
