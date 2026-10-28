<#
.SYNOPSIS
    Takes screenshots of the badge apps, for the README.

.DESCRIPTION
    Over the serial console, starts a badge app outside the menu, lets it run
    for a few seconds, then reads the screen buffer (RGB565) and saves it as a
    PNG. The badge is rebooted at the end.

    Without -App, takes every screenshot listed in docs/screenshots/captures.json.

.EXAMPLE
    ./tools/screenshot.ps1
    Retakes every screenshot in docs/screenshots/.

.EXAMPLE
    ./tools/screenshot.ps1 -App snake -Out docs/screenshots/snake.png -Seconds 5
    A single screenshot, after 5 s of play.

.EXAMPLE
    ./tools/screenshot.ps1 -App badge -Setup 'g["qr_pages"].page = 1' -Out qr.png
    -Setup runs once the app has drawn its first frame; g holds its variables.
#>
[CmdletBinding()]
param(
    # App folder in system/apps (e.g. badge, radar).
    [string]$App,
    # PNG file to write.
    [string]$Out,
    # How long the app runs before the screenshot.
    [double]$Seconds = 3,
    # MicroPython code run after launch (e.g. to open a page).
    [string]$Setup = '',
    # PNG scale (2 = 640×480, sharp pixels).
    [ValidateRange(1, 4)]
    [int]$Scale = 2,
    # Badge serial port. Detected automatically when empty.
    [string]$Port
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
# Replaced by the real screen size on every screenshot
$Width = 320
$Height = 240
$RowBytes = 640
$ChunkBytes = 3072

function Find-BadgePort {
    $ports = @(Get-PnpDevice -PresentOnly -Class Ports -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -like 'USB\VID_2E8A&PID_1101*' -and $_.FriendlyName -match '\((COM\d+)\)' } |
        ForEach-Object { $Matches[1] })
    if ($ports.Count -gt 1) { throw "Several badges plugged in ($($ports -join ', ')): choose one with -Port." }
    if ($ports.Count -eq 0) { throw "Badge not found: plug it in over USB and switch it on." }
    return $ports[0]
}

function Open-Badge([string]$SerialPort) {
    $serial = New-Object System.IO.Ports.SerialPort $SerialPort, 115200
    $serial.DtrEnable = $true
    $serial.ReadTimeout = 2000
    # A frame is ~200 KB in base64: the default 4 KB buffer would overflow
    $serial.ReadBufferSize = 1MB
    $deadline = (Get-Date).AddSeconds(15)
    while ($true) {
        try { $serial.Open(); break }
        catch { if ((Get-Date) -gt $deadline) { throw }; Start-Sleep -Seconds 1 }
    }
    return $serial
}

# Runs MicroPython code on the badge and returns what it printed. The code goes
# out as a single base64-encoded exec(): one console command, however many
# lines. It ends with a unique marker, so we wait for THIS command to finish
# rather than any prompt. A MicroPython error fails the screenshot (no stale or
# partial PNG).
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
        # The marker alone on its line (the echoed command has it in quotes)
        $done = [regex]::Match($output, "(?ms)^$([regex]::Escape($marker))\r?$")
        if ($done.Success) { return $output.Substring(0, $done.Index) }
        $failure = [regex]::Match($output, '(?s)Traceback \(most recent call last\):.*?(?=\r?\n>>> $)')
        if ($failure.Success) { throw "MicroPython error:`n$($failure.Value)" }
    }
    throw "No answer from the badge.`n$output"
}

# Standard CRC-32 (same as binascii.crc32 on the badge), computed with 64-bit
# integers: PowerShell reads 0xEDB88320 as a negative 32-bit integer.
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
    # -Setup code goes out in base64 to avoid any quoting trouble
    $setup64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($SetupCode))
    # run() is replaced: it runs -Setup, lets the app run for a few seconds
    # (badge.update() advances badge.ticks), then stops it. Apps with their own
    # loop (Snake, Mona Pet…) call badge.update() themselves: a wrapped badge
    # stops them too. Its state lives in globals: MicroPython does not allow
    # self.__dict__ in __setattr__, and every write must reach the real badge
    # (e.g. badge.default_clear in Life).
    $runner = @"
import os, sys, time, binascii, gc
os.chdir('$path')
sys.path.insert(0, '$path')
SETUP = binascii.a2b_base64('$setup64').decode()

class StopCapture(Exception):
    pass

REAL_BADGE = badge
MIN_FRAMES = 3
DEADLINE = None
FRAMES = 0

# The timer starts on the first frame, once the app is initialised (ISS joins
# the Wi-Fi first); stop after the timer AND a few frames.
def frame_done():
    global SETUP, DEADLINE, FRAMES
    if SETUP:
        code, SETUP = SETUP, ''
        exec(code, globals())
    if DEADLINE is None:
        DEADLINE = time.ticks_add(time.ticks_ms(), $ms)
    FRAMES += 1
    return FRAMES >= MIN_FRAMES and time.ticks_diff(time.ticks_ms(), DEADLINE) >= 0

class CaptureBadge:
    def __getattr__(self, name):
        return getattr(REAL_BADGE, name)

    def __setattr__(self, name, value):
        setattr(REAL_BADGE, name, value)

    def update(self, *args):
        result = REAL_BADGE.update(*args)
        if frame_done():
            raise StopCapture()
        return result

def capture_run(f):
    while True:
        REAL_BADGE.update()
        f()
        display.update()
        if frame_done():
            raise StopCapture()

g = dict(globals())
g['run'] = capture_run
g['badge'] = CaptureBadge()
g['__name__'] = 'capture'
"@
    $null = Invoke-Code $serial $runner
    # Like the menu before launching an app: low resolution by default, apps in
    # high resolution ask for it themselves
    $launch = @"
badge.mode(LORES | VSYNC)
try:
    exec(open('$path/__init__.py').read(), g)
except StopCapture:
    pass
if FRAMES < MIN_FRAMES:
    raise RuntimeError('app stopped after %d frame(s), nothing to capture' % FRAMES)
"@
    $null = Invoke-Code $serial $launch ([int]$RunSeconds + 60)

    # Real screen size: only the badge's two RGB565 modes are accepted, so a
    # damaged digit cannot produce a truncated image.
    $known = @{ '320x240' = 640; '160x120' = 320 }
    for ($attempt = 0; $attempt -lt 3; $attempt++) {
        $dims = [regex]::Match((Invoke-Code $serial "print('DIM', screen.width, screen.height, screen.stride)"), '(?m)^DIM (\d+) (\d+) (\d+)\r?$')
        if ($dims.Success -and $known["$($dims.Groups[1].Value)x$($dims.Groups[2].Value)"] -eq [int]$dims.Groups[3].Value) { break }
        $dims = $null
    }
    if (-not $dims) { throw "Screen size unreadable or unexpected." }
    $script:Width = [int]$dims.Groups[1].Value
    $script:Height = [int]$dims.Groups[2].Value
    $script:RowBytes = [int]$dims.Groups[3].Value

    # The frame goes out in "#n:crc:base64" chunks. The badge console sometimes
    # drops bytes when it goes fast: the CRC covers the index and the data, and
    # every missing or damaged chunk is requested again.
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
    if ($missing.Count -gt 0) { throw "Incomplete frame: chunks $($missing -join ', ') unreadable." }

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
    # Same PNG size whatever the app's resolution
    $Factor = $Scale * [Math]::Max(1, [int](320 / $Width))
    $bitmap = New-Object System.Drawing.Bitmap ($Width * $Factor), ($Height * $Factor), ([System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
    $rect = New-Object System.Drawing.Rectangle 0, 0, $bitmap.Width, $bitmap.Height
    $data = $bitmap.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::WriteOnly, $bitmap.PixelFormat)
    $stride = $data.Stride
    $pixels = New-Object byte[] ($stride * $bitmap.Height)
    for ($y = 0; $y -lt $Height; $y++) {
        for ($x = 0; $x -lt $Width; $x++) {
            # Little-endian RGB565: rrrrrggg gggbbbbb
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
    # Windows PowerShell returns the JSON array as one item: unroll it
    $captures = @((Get-Content $listPath -Raw -Encoding UTF8 | ConvertFrom-Json) | ForEach-Object { $_ })
    foreach ($capture in $captures) { $capture.file = Join-Path $Root $capture.file }
}

if (-not $Port) { $Port = Find-BadgePort }
$failed = @()
foreach ($capture in $captures) {
    Write-Host "Capturing $($capture.app) -> $($capture.file)"
    $serial = Open-Badge $Port
    try {
        $seconds = if ($capture.seconds) { [double]$capture.seconds } else { 3 }
        $raw = Get-Frame $serial $capture.app $seconds ([string]$capture.setup)
        $saved = Save-Png $raw $capture.file $Scale
        Write-Host "  $saved"
    }
    catch {
        # One crashing app must not stop the other screenshots
        Write-Warning "  failed: $($_.Exception.Message)"
        $failed += $capture.file
    }
    finally {
        # Reboot the badge to start from a clean state (Bluetooth, screen mode…)
        try { $serial.Write([char]3); Start-Sleep -Milliseconds 200; $serial.Write("import machine; machine.reset()`r") } catch { }
        Start-Sleep -Milliseconds 300
        try { $serial.Close() } catch { }
    }
    Start-Sleep -Seconds 8
}
Write-Host "$($captures.Count - $failed.Count) of $($captures.Count) screenshot(s) saved."
if ($failed) { throw "Failed screenshots: $($failed -join ', ')" }
