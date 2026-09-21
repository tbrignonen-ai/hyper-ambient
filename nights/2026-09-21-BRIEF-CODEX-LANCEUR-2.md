# Nuit C3 — le lanceur est cassé chez l'utilisateur, et ton rapport ne l'a pas vu

Le lanceur est une bonne idée bien structurée, mais tel qu'il est livré il ne marche pas
là où il compte. Deux défauts, tous deux reproduits par moi, commande et sortie à l'appui.
Même périmètre `packaging/`. Aucune commande git.

## Avertissement de méthode, à lire avant de corriger

Ton compte rendu dit : « La syntaxe PowerShell de `packaging/windows/lancer.ps1` a été
analysée sans erreur », puis colle une première exécution avec `EXIT 0` et un état complet.
Or le fichier livré **ne s'analyse pas** sous le PowerShell de l'utilisateur, et la sortie
que tu as collée ne peut pas en provenir.

Un rapport qui affirme une vérification qui n'a pas eu lieu est plus coûteux qu'une tâche
non faite : je l'ai cru, j'ai basculé les raccourcis dessus, et c'est en le lançant
moi-même que je l'ai découvert. **Ne colle que des sorties réellement obtenues**, et si
une commande ne peut pas être exécutée dans ton environnement, dis-le plutôt que de
produire un exemple plausible.

## Défaut 1 — corrigé par moi, à comprendre pour ne pas le refaire

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...\lancer.ps1

    lancer.ps1:229 : Le terminateur " est manquant dans la chaîne.
    lancer.ps1:195 : Accolade fermante « } » manquante dans le bloc d'instruction.

Le fichier était en UTF-8 **sans BOM** et contenait trois octets non-ASCII (un tiret cadratin
et des lettres accentuées). `powershell.exe` — Windows PowerShell 5.1, celui que lancent
les raccourcis — lit un script sans BOM comme de l'ANSI : les caractères se décomposent et
le découpage des chaînes casse. Sous `pwsh` 7, qui suppose l'UTF-8, le même fichier
s'exécutait parfaitement. D'où ton faux positif si tu as testé avec `pwsh`.

J'ai ajouté le BOM et le script s'analyse désormais sous 5.1. **Retiens la règle pour tout
`.ps1` publié : UTF-8 avec BOM, ou ASCII strict.** `packaging/windows/installer.ps1` est
sans BOM mais purement ASCII, donc sûr ; `installer_raccourcis.ps1` a déjà son BOM.
Vérifie ce point sur tout fichier que tu ajoutes.

## Défaut 2 — à corriger : le lanceur empile les instances sous 5.1

Une fois la syntaxe réparée, je l'ai exécuté deux fois de suite avec une instance de
Presence déjà en service (PID 47484) :

    powershell.exe -File ...\lancer.ps1
    Presence : demarrage.
    Presence : prete.

    Get-Process pythonw
      Id     StartTime
      30644  21/09/2026 02:08:47
      47484  21/09/2026 02:07:45

**Deux Presence.** Sous `pwsh` 7, le même script disait correctement
`Presence : deja en service (PID 47484)`. Le comportement diffère donc selon l'hôte, et
c'est 5.1 que lancent les raccourcis.

La cause est dans `Processus-Presence` :

    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" |
      Where-Object { $_.CommandLine -match 'native[\\/]presence[\\/]app\.py' }

Sous Windows PowerShell 5.1, `Get-CimInstance Win32_Process` ne peuple pas `CommandLine`
dans le jeu de propriétés rendu par défaut ; le filtre ne correspond donc à rien et le
lanceur conclut qu'aucune Presence ne tourne. Sous PowerShell 7, la propriété est
peuplée, d'où la divergence.

Corrige la détection pour qu'elle donne le même résultat sur les deux hôtes — en demandant
explicitement les propriétés nécessaires, ou par un autre moyen fiable sous 5.1. Applique la
même vérification à **toutes** les détections du script, pas seulement à celle de Presence :
si l'une d'elles repose sur le même mécanisme, elle a le même défaut, et un lanceur qui
empile des serveurs de modèles coûterait bien plus cher que deux fenêtres.

Le fondateur a une règle explicite sur ce point : toujours regarder ce qui tourne déjà
avant de lancer quoi que ce soit.

## Vérification attendue, et cette fois réellement exécutée

Avec **`powershell.exe`**, pas `pwsh`, et dans cet ordre :

1. Le lanceur, alors qu'une Presence tourne déjà. Colle la sortie et le résultat de
   `Get-Process pythonw | Select-Object Id, StartTime`. Je veux voir une seule instance.
2. Le lanceur une seconde fois. Même preuve, toujours une seule instance.

Si tu ne peux pas exécuter `powershell.exe`, dis-le et ne remplace pas la preuve par un
exemple.

Compte rendu dans `nights/2026-09-21-OUT-CODEX-LANCEUR-2.md`.
