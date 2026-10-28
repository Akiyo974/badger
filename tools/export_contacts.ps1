<#
.SYNOPSIS
    Exporte les contacts échangés avec l'app Contacts vers le PC (CSV + vCard).

.DESCRIPTION
    Lit /state/contacts.json par la console série du badge (le fichier n'est pas
    sur le lecteur USB), puis écrit contacts.csv et contacts.vcf. Le fichier vCard
    s'importe directement dans un téléphone, Outlook ou Google Contacts.
    Le badge est redémarré à la fin.

.EXAMPLE
    ./tools/export_contacts.ps1
    Écrit contacts.csv et contacts.vcf dans le dossier courant.

.EXAMPLE
    ./tools/export_contacts.ps1 -OutDir ~/Desktop
#>
[CmdletBinding()]
param(
    # Dossier où écrire les fichiers.
    [string]$OutDir = '.',
    # Port série du badge (ex. COM4). Détecté automatiquement si vide.
    [string]$Port
)

$ErrorActionPreference = 'Stop'

if (-not $Port) {
    $device = Get-PnpDevice -PresentOnly -Class Ports -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -match 'VID_2E8A' } |
        Select-Object -First 1
    if ($device -and $device.FriendlyName -match '\((COM\d+)\)') { $Port = $Matches[1] }
}
if (-not $Port) { throw "Badge introuvable : branche-le en USB et allume-le." }

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

# La première ligne est l'écho de la commande : on prend le dernier bloc <<< … >>>
$found = [regex]::Matches($output, '<<<(.*)>>>')
if ($found.Count -eq 0) { throw "Impossible de lire /state/contacts.json sur le badge." }
$cards = @(($found[$found.Count - 1].Groups[1].Value | ConvertFrom-Json).cards)

if (-not $cards) {
    Write-Host "Aucun contact sur le badge."
    return
}

function Get-Field($card, $name) {
    $value = $card.$name
    if ($null -eq $value) { '' } else { [string]$value }
}

$rows = foreach ($card in $cards) {
    $github = Get-Field $card 'github'
    [pscustomobject]@{
        Nom      = Get-Field $card 'name'
        GitHub   = if ($github) { "https://github.com/$github" } else { '' }
        LinkedIn = Get-Field $card 'linkedin'
        Site     = Get-Field $card 'website'
        Badge    = Get-Field $card 'badge'
    }
}

New-Item -ItemType Directory -Force $OutDir | Out-Null
$csvPath = Join-Path $OutDir 'contacts.csv'
$vcfPath = Join-Path $OutDir 'contacts.vcf'

$rows | Export-Csv -Path $csvPath -NoTypeInformation -Encoding UTF8

$vcards = foreach ($row in $rows) {
    $lines = @('BEGIN:VCARD', 'VERSION:3.0', "FN:$($row.Nom)", "N:$($row.Nom);;;;")
    foreach ($url in @($row.GitHub, $row.LinkedIn, $row.Site)) {
        if ($url) { $lines += "URL:$url" }
    }
    $lines += 'NOTE:Échangé avec le badge GitHub Universe ''26'
    $lines += 'END:VCARD'
    $lines -join "`r`n"
}
[IO.File]::WriteAllText((Join-Path (Resolve-Path $OutDir) 'contacts.vcf'), ($vcards -join "`r`n") + "`r`n", (New-Object Text.UTF8Encoding $false))

Write-Host "$($rows.Count) contact(s) exportés :"
Write-Host "  $csvPath"
Write-Host "  $vcfPath"
