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

# Identifiant USB du badge Universe '26 (Raspberry Pi = 2E8A, badge = 1101)
$BadgeUsbId = 'VID_2E8A&PID_1101'
$DriveLabel = 'BADGER'
$MountTimeoutSeconds = 30
$Source = (Resolve-Path (Join-Path $PSScriptRoot '..\system')).Path.TrimEnd('\')

# Ports série des badges branchés, avec le numéro de série USB qui relie
# chaque port à son lecteur.
function Get-BadgePorts {
    Get-PnpDevice -PresentOnly -Class Ports -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -like "USB\$BadgeUsbId*" -and $_.FriendlyName -match '\((COM\d+)\)' } |
        ForEach-Object {
            $parent = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_Device_Parent -ErrorAction SilentlyContinue).Data
            [pscustomobject]@{ Port = $Matches[1]; Serial = if ($parent) { ($parent -split '\\')[-1] } else { '' } }
        }
}

function Find-BadgeDrive([string]$Serial) {
    $drives = @(Get-Volume -ErrorAction SilentlyContinue |
        Where-Object { $_.FileSystemLabel -eq $DriveLabel -and $_.DriveLetter -and (Test-Path "$($_.DriveLetter):\main.py") } |
        Where-Object {
            if (-not $Serial) { return $true }
            $disk = Get-Partition -DriveLetter $_.DriveLetter -ErrorAction SilentlyContinue | Get-Disk -ErrorAction SilentlyContinue
            $disk -and $disk.Path -match [regex]::Escape($Serial)
        })
    if ($drives.Count -gt 1) { throw "Plusieurs lecteurs $DriveLabel trouvés : débranche les autres badges ou précise -Port." }
    if ($drives.Count -eq 1) { return "$($drives[0].DriveLetter):" }
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

# Un -Port donné à la main n'est jamais remplacé. Sinon, il faut un seul badge
# branché : on ne choisit pas au hasard entre plusieurs appareils.
$ports = @(Get-BadgePorts)
if ($Port) {
    $serial = ($ports | Where-Object Port -eq $Port | Select-Object -First 1).Serial
}
elseif ($ports.Count -gt 1) {
    throw "Plusieurs badges branchés ($(($ports.Port) -join ', ')) : précise lequel avec -Port."
}
elseif ($ports.Count -eq 1) {
    $Port = $ports[0].Port
    $serial = $ports[0].Serial
}
# Sans numéro de série, impossible de savoir quel lecteur va avec ce port :
# on pourrait copier sur un badge et en redémarrer un autre.
if ($Port -and -not $serial) {
    throw "Impossible d'identifier le badge sur $Port (numéro de série USB introuvable). Vérifie le port ou débranche les autres appareils."
}

$drive = Find-BadgeDrive $serial
if (-not $drive) {
    if (-not $Port) { throw "Badge introuvable : branche-le en USB et allume-le." }
    Write-Host "Passage du badge en mode clé USB ($Port)..."
    Send-Repl $Port 'import powman; powman.reset_into_msc()'
    $deadline = (Get-Date).AddSeconds($MountTimeoutSeconds)
    while (-not $drive -and (Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 1
        $drive = Find-BadgeDrive $serial
    }
    if (-not $drive) { throw "Le lecteur $DriveLabel n'est pas apparu après $MountTimeoutSeconds s." }
}
Write-Host "Badge trouvé : lecteur $drive, port $Port"

# -Only est normalisé (., .., barres) et doit rester à l'intérieur de system/
$from = $Source
if ($Only) {
    $from = [IO.Path]::GetFullPath((Join-Path $Source ($Only -replace '/', '\'))).TrimEnd('\')
    if ($from -ne $Source -and -not $from.StartsWith("$Source\", [StringComparison]::OrdinalIgnoreCase)) {
        throw "-Only doit désigner un dossier de system/ : $Only"
    }
    if (-not (Test-Path $from -PathType Container)) { throw "Dossier introuvable dans system/ : $Only" }
}
$to = Join-Path "$drive\" $from.Substring($Source.Length).TrimStart('\')

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

# Vide le cache d'écriture de Windows avant de redémarrer le badge. Si ça échoue,
# redémarrer pourrait corrompre les fichiers : on s'arrête sans redémarrer.
try {
    Write-VolumeCache -DriveLetter $drive[0] -ErrorAction Stop
}
catch {
    throw "Impossible de finir l'écriture sur $drive ($($_.Exception.Message)). Éjecte le lecteur $DriveLabel depuis l'Explorateur, puis redémarre le badge."
}

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
