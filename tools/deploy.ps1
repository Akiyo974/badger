<#
.SYNOPSIS
    Deploys the repo's system/ folder to the badge, then reboots it.

.DESCRIPTION
    Finds the badge plugged in over USB (serial port and BADGER drive). If it is
    not in USB drive mode, switches it there. Then copies only the files that
    changed, never touching secrets.py nor deleting anything on the badge, and
    reboots the badge into normal mode.

.EXAMPLE
    ./tools/deploy.ps1
    Deploys all of system/ and reboots the badge.

.EXAMPLE
    ./tools/deploy.ps1 -Only apps/badge
    Copies only the Badge app.

.EXAMPLE
    ./tools/deploy.ps1 -DryRun
    Shows what would be copied, without writing anything.
#>
[CmdletBinding()]
param(
    # Badge serial port (e.g. COM4). Detected automatically when empty.
    [string]$Port,
    # Single folder of system/ to copy (e.g. apps/badge).
    [string]$Only,
    # Dry run: list the files without copying them.
    [switch]$DryRun,
    # Leave the badge in USB drive mode after copying.
    [switch]$NoReboot
)

$ErrorActionPreference = 'Stop'

# USB id of the Universe '26 badge (Raspberry Pi = 2E8A, badge = 1101)
$BadgeUsbId = 'VID_2E8A&PID_1101'
$DriveLabel = 'BADGER'
$MountTimeoutSeconds = 30
$Source = (Resolve-Path (Join-Path $PSScriptRoot '..\system')).Path.TrimEnd('\')

# Serial ports of the plugged-in badges, with the USB serial number that ties
# each port to its drive.
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
    if ($drives.Count -gt 1) { throw "Several $DriveLabel drives found: unplug the other badges or pass -Port." }
    if ($drives.Count -eq 1) { return "$($drives[0].DriveLetter):" }
}

# Interrupts the running app (Ctrl-C) and runs one line in the MicroPython console.
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
        # The badge often reboots before the port is closed
        try { $serial.Close() } catch { }
    }
}

# A -Port given by hand is never replaced. Otherwise exactly one badge must be
# plugged in: we never pick at random between several devices.
$ports = @(Get-BadgePorts)
if ($Port) {
    $serial = ($ports | Where-Object Port -eq $Port | Select-Object -First 1).Serial
}
elseif ($ports.Count -gt 1) {
    throw "Several badges plugged in ($(($ports.Port) -join ', ')): choose one with -Port."
}
elseif ($ports.Count -eq 1) {
    $Port = $ports[0].Port
    $serial = $ports[0].Serial
}
# Without a serial number there is no way to know which drive belongs to this
# port: we could copy to one badge and reboot another.
if ($Port -and -not $serial) {
    throw "Cannot identify the badge on $Port (USB serial number not found). Check the port or unplug other devices."
}

$drive = Find-BadgeDrive $serial
$switched = -not $drive
if (-not $drive) {
    if (-not $Port) { throw "Badge not found: plug it in over USB and switch it on." }
    Write-Host "Switching the badge to USB drive mode ($Port)..."
    Send-Repl $Port 'import powman; powman.reset_into_msc()'
    $deadline = (Get-Date).AddSeconds($MountTimeoutSeconds)
    while (-not $drive -and (Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 1
        $drive = Find-BadgeDrive $serial
    }
    if (-not $drive) { throw "The $DriveLabel drive did not show up after $MountTimeoutSeconds s." }
}
Write-Host "Badge found: drive $drive, port $Port"

# -Only is normalised (., .., slashes) and must stay inside system/
$from = $Source
if ($Only) {
    $from = [IO.Path]::GetFullPath((Join-Path $Source ($Only -replace '/', '\'))).TrimEnd('\')
    if ($from -ne $Source -and -not $from.StartsWith("$Source\", [StringComparison]::OrdinalIgnoreCase)) {
        throw "-Only must point to a folder of system/: $Only"
    }
    if (-not (Test-Path $from -PathType Container)) { throw "Folder not found in system/: $Only" }
}
$to = Join-Path "$drive\" $from.Substring($Source.Length).TrimStart('\')

# Compare content (not dates, which git changes on every checkout) to copy only
# what really changed. Nothing is ever deleted on the badge.
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
    Write-Host "Nothing to copy: the badge is already up to date."
}
foreach ($file in $changed) {
    Write-Host "  $($file.Path)"
    if (-not $DryRun) {
        # Files at the root of system/ go straight to the drive root, which New-Item rejects
        $folder = Split-Path $file.Target
        if (-not (Test-Path $folder)) { New-Item -ItemType Directory -Force $folder | Out-Null }
        Copy-Item $file.Source $file.Target -Force
    }
}

if ($DryRun) {
    Write-Host "Dry run: $($changed.Count) file(s) would be copied, nothing was written."
    # Put the badge back the way we found it
    if ($switched -and -not $NoReboot) { Send-Repl $Port 'import machine; machine.reset()' }
    return
}
if ($changed) { Write-Host "$($changed.Count) file(s) copied." }

# Flush Windows' write cache before rebooting the badge. If that fails,
# rebooting could corrupt files: stop without rebooting.
try {
    Write-VolumeCache -DriveLetter $drive[0] -ErrorAction Stop
}
catch {
    throw "Could not finish writing to $drive ($($_.Exception.Message)). Eject the $DriveLabel drive from Explorer, then restart the badge."
}

if ($NoReboot) {
    Write-Host "Copy done. The badge stays in USB drive mode."
}
elseif ($Port) {
    Send-Repl $Port 'import machine; machine.reset()'
    Write-Host "Copy done. The badge is rebooting."
}
else {
    Write-Warning "Copy done, but no serial port found: restart the badge by hand."
}
