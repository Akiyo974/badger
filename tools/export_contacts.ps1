<#
.SYNOPSIS
    Exports the cards swapped with the Contacts app to the PC (CSV + vCard).

.DESCRIPTION
    Reads /state/contacts.json over the badge's serial console (the file is not
    on the USB drive), then writes contacts.csv and contacts.vcf. The vCard file
    imports straight into a phone, Outlook or Google Contacts.
    The badge is rebooted at the end.

.EXAMPLE
    ./tools/export_contacts.ps1
    Writes contacts.csv and contacts.vcf to the current folder.

.EXAMPLE
    ./tools/export_contacts.ps1 -OutDir ~/Desktop
#>
[CmdletBinding()]
param(
    # Folder to write the files to.
    [string]$OutDir = '.',
    # Badge serial port (e.g. COM4). Detected automatically when empty.
    [string]$Port
)

$ErrorActionPreference = 'Stop'

if (-not $Port) {
    # Only the Universe '26 badge, and only when exactly one is plugged in
    $ports = @(Get-PnpDevice -PresentOnly -Class Ports -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -like 'USB\VID_2E8A&PID_1101*' -and $_.FriendlyName -match '\((COM\d+)\)' } |
        ForEach-Object { $Matches[1] })
    if ($ports.Count -gt 1) { throw "Several badges plugged in ($($ports -join ', ')): choose one with -Port." }
    if ($ports.Count -eq 1) { $Port = $ports[0] }
}
if (-not $Port) { throw "Badge not found: plug it in over USB and switch it on." }

$serial = New-Object System.IO.Ports.SerialPort $Port, 115200
$serial.DtrEnable = $true
$serial.Encoding = [System.Text.Encoding]::UTF8
$serial.Open()
try {
    $serial.Write([char]3); Start-Sleep -Milliseconds 300
    $serial.Write([char]3); Start-Sleep -Milliseconds 300
    $null = $serial.ReadExisting()
    $serial.Write("print('<<<' + open('/state/contacts.json').read() + '>>>')`r")
    $output = ''
    $deadline = (Get-Date).AddSeconds(10)
    while ($output -notmatch '>>>\s*\r?\n' -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 200
        $output += $serial.ReadExisting()
    }
    $serial.Write("import machine; machine.reset()`r")
    Start-Sleep -Milliseconds 300
}
finally {
    try { $serial.Close() } catch { }
}

# The first line is the echoed command: take the last <<< … >>> block
$found = [regex]::Matches($output, '<<<(.*)>>>')
if ($found.Count -eq 0) { throw "Could not read /state/contacts.json on the badge." }
$cards = @(($found[$found.Count - 1].Groups[1].Value | ConvertFrom-Json).cards)

if (-not $cards) {
    Write-Host "No contacts on the badge."
    return
}

function Get-Field($card, $name) {
    $value = $card.$name
    if ($null -eq $value) { '' } else { [string]$value }
}

$rows = foreach ($card in $cards) {
    $github = Get-Field $card 'github'
    [pscustomobject]@{
        Name     = Get-Field $card 'name'
        GitHub   = if ($github) { "https://github.com/$github" } else { '' }
        LinkedIn = Get-Field $card 'linkedin'
        Website  = Get-Field $card 'website'
        Badge    = Get-Field $card 'badge'
    }
}

New-Item -ItemType Directory -Force $OutDir | Out-Null
$csvPath = Join-Path $OutDir 'contacts.csv'
$vcfPath = Join-Path $OutDir 'contacts.vcf'

$rows | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8

$vcards = foreach ($row in $rows) {
    $lines = @('BEGIN:VCARD', 'VERSION:3.0', "FN:$($row.Name)", "N:$($row.Name);;;;")
    foreach ($url in @($row.GitHub, $row.LinkedIn, $row.Website)) {
        if ($url) { $lines += "URL:$url" }
    }
    $lines += 'NOTE:Swapped with the GitHub Universe ''26 badge'
    $lines += 'END:VCARD'
    $lines -join "`r`n"
}
[IO.File]::WriteAllText((Join-Path (Resolve-Path $OutDir) 'contacts.vcf'), ($vcards -join "`r`n") + "`r`n", (New-Object Text.UTF8Encoding $false))

Write-Host "$($rows.Count) contact(s) exported:"
Write-Host "  $csvPath"
Write-Host "  $vcfPath"
