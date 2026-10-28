<#
.SYNOPSIS
    Déploie le dossier system/ du repo sur le badge, puis le redémarre.

.DESCRIPTION
    Trouve le badge branché en USB (port série et lecteur BADGER). S'il n'est pas
    en mode clé USB, il l'y met tout seul. Copie ensuite uniquement les fichiers
    modifiés, sans jamais toucher à secrets.py ni supprimer de fichier sur le badge,
    puis redémarre le badge en mode normal.

.EXAMPLE
    ./tools/deploy.ps1
    Déploie tout system/ et redémarre le badge.

.EXAMPLE
    ./tools/deploy.ps1 -Only apps/badge
    Ne copie que l'app Badge.

.EXAMPLE
    ./tools/deploy.ps1 -DryRun
    Affiche ce qui serait copié, sans rien écrire.
#>
[CmdletBinding()]
param(
    # Port série du badge (ex. COM4). Détecté automatiquement si vide.
    [string]$Port,
    # Sous-dossier de system/ à copier seul (ex. apps/badge).
    [string]$Only,
    # Simulation : liste les fichiers sans les copier.
    [switch]$DryRun,
    # Laisse le badge en mode clé USB après la copie.
    [switch]$NoReboot
)

$ErrorActionPreference = 'Stop'

$BadgeVid = 'VID_2E8A'
$DriveLabel = 'BADGER'
$MountTimeoutSeconds = 30
$Source = (Resolve-Path (Join-Path $PSScriptRoot '..\system')).Path

function Find-BadgePort {
    $device = Get-PnpDevice -PresentOnly -Class Ports -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -match $BadgeVid } |
        Select-Object -First 1
    if ($device -and $device.FriendlyName -match '\((COM\d+)\)') {
        return $Matches[1]
    }
}

function Find-BadgeDrive {
    $volume = Get-Volume -ErrorAction SilentlyContinue |
        Where-Object { $_.FileSystemLabel -eq $DriveLabel -and $_.DriveLetter } |
        Select-Object -First 1
    if ($volume -and (Test-Path "$($volume.DriveLetter):\main.py")) {
        return "$($volume.DriveLetter):"
    }
}

# Interrompt l'app en cours (Ctrl-C) et exécute une ligne dans la console MicroPython.
function Send-Repl([string]$SerialPort, [string]$Code) {
    $serial = New-Object System.IO.Ports.SerialPort $SerialPort, 115200
    $serial.DtrEnable = $true
    $serial.Open()
    try {
        $serial.Write([char]3); Start-Sleep -Milliseconds 300
        $serial.Write([char]3); Start-Sleep -Milliseconds 300
        $serial.Write("$Code`r"); Start-Sleep -Milliseconds 500
    }
    finally {
        # Le badge redémarre souvent avant la fermeture du port
        try { $serial.Close() } catch { }
    }
}

if (-not $Port) { $Port = Find-BadgePort }

$drive = Find-BadgeDrive
if (-not $drive) {
    if (-not $Port) { throw "Badge introuvable : branche-le en USB et allume-le." }
    Write-Host "Passage du badge en mode clé USB ($Port)..."
    Send-Repl $Port 'import powman; powman.reset_into_msc()'
    $deadline = (Get-Date).AddSeconds($MountTimeoutSeconds)
    while (-not $drive -and (Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 1
        $drive = Find-BadgeDrive
    }
    if (-not $drive) { throw "Le lecteur $DriveLabel n'est pas apparu après $MountTimeoutSeconds s." }
    $Port = Find-BadgePort
}
Write-Host "Badge trouvé : lecteur $drive, port $Port"

$from = $Source
$to = "$drive\"
if ($Only) {
    $relative = $Only.Trim('/\') -replace '/', '\'
    $from = Join-Path $Source $relative
    $to = Join-Path $to $relative
    if (-not (Test-Path $from -PathType Container)) { throw "Dossier introuvable dans system/ : $Only" }
}

# On compare le contenu (et pas la date, que git change à chaque checkout) pour ne
# copier que ce qui a vraiment changé. On ne supprime jamais rien sur le badge.
$skipDirs = '\\(System Volume Information|\.ruff_cache|__pycache__)\\'
$changed = @()
Get-ChildItem $from -Recurse -File | ForEach-Object {
    if ($_.FullName -match $skipDirs -or $_.Name -eq 'secrets.py' -or $_.Extension -eq '.tmp') { return }
    $relative = $_.FullName.Substring($from.Length).TrimStart('\')
    $target = Join-Path $to $relative
    $same = (Test-Path $target) -and
        ((Get-Item $target).Length -eq $_.Length) -and
        ((Get-FileHash $target).Hash -eq (Get-FileHash $_.FullName).Hash)
    if (-not $same) { $changed += [pscustomobject]@{ Source = $_.FullName; Target = $target; Path = $relative } }
}

if (-not $changed) {
    Write-Host "Rien à copier : le badge est déjà à jour."
}
foreach ($file in $changed) {
    Write-Host "  $($file.Path)"
    if (-not $DryRun) {
        New-Item -ItemType Directory -Force (Split-Path $file.Target) | Out-Null
        Copy-Item $file.Source $file.Target -Force
    }
}

if ($DryRun) {
    Write-Host "Simulation : $($changed.Count) fichier(s) seraient copiés, rien n'a été écrit."
    return
}
if ($changed) { Write-Host "$($changed.Count) fichier(s) copiés." }

# Vide le cache d'écriture de Windows avant de redémarrer le badge
try { Write-VolumeCache -DriveLetter $drive[0] } catch { Start-Sleep -Seconds 2 }

if ($NoReboot) {
    Write-Host "Copie terminée. Le badge reste en mode clé USB."
}
elseif ($Port) {
    Send-Repl $Port 'import machine; machine.reset()'
    Write-Host "Copie terminée. Le badge redémarre."
}
else {
    Write-Warning "Copie terminée, mais port série introuvable : redémarre le badge à la main."
}
