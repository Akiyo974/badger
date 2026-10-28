<#
.SYNOPSIS
    Prend des captures d'écran des apps du badge, pour le README.

.DESCRIPTION
    Par la console série, lance une app du badge en dehors du menu, la fait
    tourner quelques secondes, puis récupère l'image de l'écran (320×240,
    RGB565) et l'enregistre en PNG. Le badge est redémarré à la fin.

    Sans -App, prend toutes les captures listées dans docs/screenshots/captures.json.

.EXAMPLE
    ./tools/screenshot.ps1
    Refait toutes les captures de docs/screenshots/.

.EXAMPLE
    ./tools/screenshot.ps1 -App snake -Out docs/screenshots/snake.png -Seconds 5
    Une seule capture, après 5 s de jeu.

.EXAMPLE
    ./tools/screenshot.ps1 -App badge -Setup 'g["qr_pages"].page = 1' -Out qr.png
    -Setup s'exécute après le lancement de l'app ; g contient ses variables.
#>
[CmdletBinding()]
param(
    # Dossier de l'app dans system/apps (ex. badge, radar).
    [string]$App,
    # Fichier PNG à écrire.
    [string]$Out,
    # Durée pendant laquelle l'app tourne avant la capture.
    [double]$Seconds = 3,
    # Code MicroPython exécuté après le lancement (ex. pour ouvrir une page).
    [string]$Setup = '',
    # Agrandissement du PNG (2 = 640×480, pixels nets).
    [ValidateRange(1, 4)]
    [int]$Scale = 2,
    # Port série du badge. Détecté automatiquement si vide.
    [string]$Port
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
# Remplacés par la taille réelle de l'écran à chaque capture
$Width = 320
$Height = 240
$RowBytes = 640
$ChunkBytes = 3072

function Find-BadgePort {
    $ports = @(Get-PnpDevice -PresentOnly -Class Ports -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -like 'USB\VID_2E8A&PID_1101*' -and $_.FriendlyName -match '\((COM\d+)\)' } |
        ForEach-Object { $Matches[1] })
    if ($ports.Count -gt 1) { throw "Plusieurs badges branchés ($($ports -join ', ')) : précise lequel avec -Port." }
    if ($ports.Count -eq 0) { throw "Badge introuvable : branche-le en USB et allume-le." }
    return $ports[0]
}

function Open-Badge([string]$SerialPort) {
    $serial = New-Object System.IO.Ports.SerialPort $SerialPort, 115200
    $serial.DtrEnable = $true
    $serial.ReadTimeout = 2000
    # Une image fait ~200 Ko en base64 : le tampon par défaut (4 Ko) déborderait
    $serial.ReadBufferSize = 1MB
    $deadline = (Get-Date).AddSeconds(15)
    while ($true) {
        try { $serial.Open(); break }
        catch { if ((Get-Date) -gt $deadline) { throw }; Start-Sleep -Seconds 1 }
    }
    return $serial
}

# Exécute du code MicroPython sur le badge et renvoie ce qu'il a affiché. Le code
# part en un seul exec() encodé en base64 : une seule commande pour la console,
# quel que soit le nombre de lignes. Il se termine par un marqueur unique, si
# bien qu'on attend la fin de CETTE commande et pas n'importe quelle invite.
# Une erreur MicroPython fait échouer la capture (pas de PNG ancien ou incomplet).
$script:CommandId = 0
function Invoke-Code($serial, [string]$Code, [int]$TimeoutSeconds = 30) {
    $script:CommandId++
    $marker = "@@done-$script:CommandId@@"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Code))
    $null = $serial.ReadExisting()
    $serial.Write("exec(__import__('binascii').a2b_base64('$encoded').decode(), globals()); print('$marker')`r")
    $output = ''
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 20
        $output += $serial.ReadExisting()
        # Le marqueur seul sur sa ligne (l'écho de la commande le contient entre guillemets)
        $done = [regex]::Match($output, "(?ms)^$([regex]::Escape($marker))\r?$")
        if ($done.Success) { return $output.Substring(0, $done.Index) }
        $failure = [regex]::Match($output, '(?s)Traceback \(most recent call last\):.*?(?=\r?\n>>> $)')
        if ($failure.Success) { throw "Erreur MicroPython :`n$($failure.Value)" }
    }
    throw "Pas de réponse du badge.`n$output"
}

# CRC-32 standard (le même que binascii.crc32 côté badge), calculé en entiers
# 64 bits : PowerShell lit 0xEDB88320 comme un entier 32 bits négatif.
$Crc32Poly = [long]3988292384
$Crc32Mask = [long]4294967295
$Crc32Table = [long[]](0..255 | ForEach-Object {
    $c = [long]$_
    for ($k = 0; $k -lt 8; $k++) { $c = if ($c -band 1) { $Crc32Poly -bxor ($c -shr 1) } else { $c -shr 1 } }
    $c
})
function Get-Crc32([byte[]]$Bytes) {
    $crc = $Crc32Mask
    foreach ($b in $Bytes) { $crc = $Crc32Table[($crc -bxor $b) -band 0xFF] -bxor ($crc -shr 8) }
    return $crc -bxor $Crc32Mask
}

function Get-Frame($serial, [string]$AppName, [double]$RunSeconds, [string]$SetupCode) {
    $serial.Write([char]3); Start-Sleep -Milliseconds 400
    $serial.Write([char]3); Start-Sleep -Milliseconds 400
    $null = Invoke-Code $serial 'pass'

    $path = "/system/apps/$AppName"
    $ms = [int]($RunSeconds * 1000)
    # Le code de -Setup passe en base64 pour éviter tout souci de guillemets
    $setup64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($SetupCode))
    # run() est remplacé : il exécute -Setup, fait tourner l'app quelques secondes
    # (badge.update() fait avancer badge.ticks) puis l'arrête. Les apps qui ont
    # leur propre boucle (Snake, Mona Pet…) appellent badge.update() elles-mêmes :
    # un badge « enveloppé » les arrête aussi. Son état vit dans des globales :
    # MicroPython ne permet pas self.__dict__ dans __setattr__, et toutes les
    # écritures doivent aller au vrai badge (ex. badge.default_clear dans Life).
    $runner = @"
import os, sys, time, binascii, gc
os.chdir('$path')
sys.path.insert(0, '$path')
SETUP = binascii.a2b_base64('$setup64').decode()

class StopCapture(Exception):
    pass

def run_setup():
    global SETUP
    if SETUP:
        code, SETUP = SETUP, ''
        exec(code, globals())

REAL_BADGE = badge
DEADLINE = time.ticks_add(time.ticks_ms(), $ms)

class CaptureBadge:
    def __getattr__(self, name):
        return getattr(REAL_BADGE, name)

    def __setattr__(self, name, value):
        setattr(REAL_BADGE, name, value)

    def update(self, *args):
        run_setup()
        result = REAL_BADGE.update(*args)
        if time.ticks_diff(time.ticks_ms(), DEADLINE) >= 0:
            raise StopCapture()
        return result

def capture_run(f):
    run_setup()
    while time.ticks_diff(time.ticks_ms(), DEADLINE) < 0:
        REAL_BADGE.update()
        f()
        display.update()
    raise StopCapture()

g = dict(globals())
g['run'] = capture_run
g['badge'] = CaptureBadge()
g['__name__'] = 'capture'
"@
    $null = Invoke-Code $serial $runner
    # Comme le menu avant de lancer une app : basse résolution par défaut,
    # les apps en haute résolution la demandent elles-mêmes
    $launch = @"
badge.mode(LORES | VSYNC)
DEADLINE = time.ticks_add(time.ticks_ms(), $ms)
try:
    exec(open('$path/__init__.py').read(), g)
except StopCapture:
    pass
"@
    $null = Invoke-Code $serial $launch ([int]$RunSeconds + 60)

    # Taille réelle de l'écran : seuls les deux modes RGB565 du badge sont
    # acceptés, pour qu'un chiffre abîmé ne donne pas une image tronquée.
    $known = @{ '320x240' = 640; '160x120' = 320 }
    for ($attempt = 0; $attempt -lt 3; $attempt++) {
        $dims = [regex]::Match((Invoke-Code $serial "print('DIM', screen.width, screen.height, screen.stride)"), '(?m)^DIM (\d+) (\d+) (\d+)\r?$')
        if ($dims.Success -and $known["$($dims.Groups[1].Value)x$($dims.Groups[2].Value)"] -eq [int]$dims.Groups[3].Value) { break }
        $dims = $null
    }
    if (-not $dims) { throw "Taille de l'écran illisible ou inattendue." }
    $script:Width = [int]$dims.Groups[1].Value
    $script:Height = [int]$dims.Groups[2].Value
    $script:RowBytes = [int]$dims.Groups[3].Value

    # L'image part en morceaux « #n:crc:base64 ». La console du badge perd parfois
    # des octets quand elle va vite : le CRC couvre le numéro et les données, et
    # chaque morceau absent ou abîmé est redemandé.
    $total = $Height * $RowBytes
    $count = [Math]::Ceiling($total / $ChunkBytes)
    $chunker = @"
r = bytes(screen.raw)[:$total]
gc.collect()

def chunk(n):
    data = r[n * ${ChunkBytes}:(n + 1) * ${ChunkBytes}]
    print('#%d:%08x:%s' % (n, binascii.crc32(b'%d:' % n + data), binascii.b2a_base64(data).decode().strip()))
"@
    $null = Invoke-Code $serial $chunker
    $chunks = @{}
    Read-Chunks (Invoke-Code $serial "for n in range($count): chunk(n)" 60) $chunks
    for ($attempt = 0; $attempt -lt 5; $attempt++) {
        $missing = @(0..($count - 1) | Where-Object { -not $chunks.ContainsKey($_) })
        if ($missing.Count -eq 0) { break }
        foreach ($n in $missing) { Read-Chunks (Invoke-Code $serial "chunk($n)") $chunks }
    }
    $missing = @(0..($count - 1) | Where-Object { -not $chunks.ContainsKey($_) })
    if ($missing.Count -gt 0) { throw "Image incomplète : morceaux $($missing -join ', ') illisibles." }

    $bytes = New-Object byte[] $total
    foreach ($n in $chunks.Keys) { [Array]::Copy($chunks[$n], 0, $bytes, $n * $ChunkBytes, $chunks[$n].Length) }
    return , $bytes
}

function Read-Chunks([string]$Text, [hashtable]$Chunks) {
    $total = $Height * $RowBytes
    foreach ($match in [regex]::Matches($Text, '(?m)^#(\d+):([0-9a-f]{8}):([A-Za-z0-9+/=]+)\r?$')) {
        $n = [int]$match.Groups[1].Value
        $expected = [Math]::Min($ChunkBytes, $total - $n * $ChunkBytes)
        if ($expected -le 0) { continue }
        try { $data = [Convert]::FromBase64String($match.Groups[3].Value) } catch { continue }
        if ($data.Length -ne $expected) { continue }
        $signed = [Text.Encoding]::ASCII.GetBytes("${n}:") + $data
        if ((Get-Crc32 $signed) -eq [Convert]::ToInt64($match.Groups[2].Value, 16)) { $Chunks[$n] = $data }
    }
}

function Save-Png([byte[]]$Raw, [string]$Path, [int]$Scale) {
    # Même taille de PNG quelle que soit la résolution de l'app
    $Factor = $Scale * [Math]::Max(1, [int](320 / $Width))
    $bitmap = New-Object System.Drawing.Bitmap ($Width * $Factor), ($Height * $Factor), ([System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
    $rect = New-Object System.Drawing.Rectangle 0, 0, $bitmap.Width, $bitmap.Height
    $data = $bitmap.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::WriteOnly, $bitmap.PixelFormat)
    $stride = $data.Stride
    $pixels = New-Object byte[] ($stride * $bitmap.Height)
    for ($y = 0; $y -lt $Height; $y++) {
        for ($x = 0; $x -lt $Width; $x++) {
            # RGB565 petit-boutiste : rrrrrggg gggbbbbb
            $i = $y * $RowBytes + $x * 2
            $v = [int]$Raw[$i] -bor ([int]$Raw[$i + 1] -shl 8)
            $r = (($v -shr 11) -band 0x1F) * 255 / 31
            $g = (($v -shr 5) -band 0x3F) * 255 / 63
            $b = ($v -band 0x1F) * 255 / 31
            for ($dy = 0; $dy -lt $Factor; $dy++) {
                $row = ($y * $Factor + $dy) * $stride
                for ($dx = 0; $dx -lt $Factor; $dx++) {
                    $o = $row + ($x * $Factor + $dx) * 3
                    $pixels[$o] = [byte]$b; $pixels[$o + 1] = [byte]$g; $pixels[$o + 2] = [byte]$r
                }
            }
        }
    }
    [System.Runtime.InteropServices.Marshal]::Copy($pixels, 0, $data.Scan0, $pixels.Length)
    $bitmap.UnlockBits($data)
    $full = if ([IO.Path]::IsPathRooted($Path)) { $Path } else { Join-Path (Get-Location) $Path }
    $full = [IO.Path]::GetFullPath($full)
    New-Item -ItemType Directory -Force (Split-Path $full) | Out-Null
    $bitmap.Save($full, [System.Drawing.Imaging.ImageFormat]::Png)
    $bitmap.Dispose()
    return $full
}

if ($App) {
    if (-not $Out) { $Out = "docs/screenshots/$App.png" }
    $captures = @([pscustomobject]@{ app = $App; file = $Out; seconds = $Seconds; setup = $Setup })
}
else {
    $listPath = Join-Path $Root 'docs\screenshots\captures.json'
    # Windows PowerShell renvoie le tableau JSON d'un bloc : on le déroule
    $captures = @((Get-Content $listPath -Raw -Encoding UTF8 | ConvertFrom-Json) | ForEach-Object { $_ })
    foreach ($capture in $captures) { $capture.file = Join-Path $Root $capture.file }
}

if (-not $Port) { $Port = Find-BadgePort }
$failed = @()
foreach ($capture in $captures) {
    Write-Host "Capture de $($capture.app) -> $($capture.file)"
    $serial = Open-Badge $Port
    try {
        $seconds = if ($capture.seconds) { [double]$capture.seconds } else { 3 }
        $raw = Get-Frame $serial $capture.app $seconds ([string]$capture.setup)
        $saved = Save-Png $raw $capture.file $Scale
        Write-Host "  $saved"
    }
    catch {
        # Une app qui plante ne doit pas empêcher les autres captures
        Write-Warning "  échec : $($_.Exception.Message)"
        $failed += $capture.file
    }
    finally {
        # Redémarre le badge pour repartir d'un état propre (Bluetooth, mode écran…)
        try { $serial.Write([char]3); Start-Sleep -Milliseconds 200; $serial.Write("import machine; machine.reset()`r") } catch { }
        Start-Sleep -Milliseconds 300
        try { $serial.Close() } catch { }
    }
    Start-Sleep -Seconds 8
}
Write-Host "$($captures.Count - $failed.Count) capture(s) enregistrée(s) sur $($captures.Count)."
if ($failed) { throw "Captures en échec : $($failed -join ', ')" }
