<#
  produce.ps1 — build one Invisible Systems video end to end (no upload).

  Usage:
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\produce.ps1 -Slug 2026-09-03__why-the-other-lane-looks-faster

  Expects in videos\<Slug>\ :
    animation.html
    audio\narration.json
    audio\sfx-cues.tsv
  Produces:
    <Slug>-silent.mp4, audio\voiceover.wav, audio\final-mix.wav,
    <Slug>-WITH-AUDIO.mp4, verification-report.md
#>
param(
  [Parameter(Mandatory = $true)][string]$Slug,
  [int]$Fps = 24,
  [int]$Width = 1080,
  [int]$Height = 1920,
  [double]$Duration = 60.0,
  [string]$Voice = "en-US-AvaNeural",
  [int]$Workers = 4
)

$ErrorActionPreference = 'Stop'
# interpreter: $env:AUTOCHANNEL_PYTHON (set by 20_produce.py / run_daily.py / CI),
# else a local Windows install, else whatever "python" resolves to on PATH.
$py = $env:AUTOCHANNEL_PYTHON
if (-not $py) {
  $local = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
  if (Test-Path $local) { $py = $local } else { $py = "python" }
}
$root  = Split-Path -Parent $PSScriptRoot
$lib   = Join-Path $PSScriptRoot 'lib'
$proj  = Join-Path $root "videos\$Slug"
$audio = Join-Path $proj 'audio'

if (-not (Test-Path $proj)) { throw "No project folder: $proj" }
foreach ($f in @("$proj\animation.html", "$audio\narration.json", "$audio\sfx-cues.tsv")) {
  if (-not (Test-Path $f)) { throw "Missing required input: $f" }
}

$silent    = Join-Path $proj "$Slug-silent.mp4"
$withAudio = Join-Path $proj "$Slug-WITH-AUDIO.mp4"
$voiceover = Join-Path $audio 'voiceover.wav'
$finalMix  = Join-Path $audio 'final-mix.wav'
$report    = Join-Path $proj 'verification-report.md'
$bgm       = Join-Path $root 'assets\audio\bgm-educational.mp3'
$sfxDir    = Join-Path $root 'assets\audio\sfx'

$sw = [Diagnostics.Stopwatch]::StartNew()

Write-Host "=== [1/5] render animation -> silent mp4 ===" -ForegroundColor Cyan
& $py "$lib\render_seek.py" "$proj\animation.html" `
    --output $silent --duration $Duration --fps $Fps --width $Width --height $Height --workers $Workers
if ($LASTEXITCODE -ne 0) { throw "render_seek failed" }

Write-Host "=== [2/5] TTS narration -> voiceover.wav ===" -ForegroundColor Cyan
& $py "$lib\generate_voiceover.py" "$audio\narration.json" --output-dir $audio --voice $Voice --duration $Duration
if ($LASTEXITCODE -ne 0) { throw "generate_voiceover failed" }
# report measured per-scene TTS lengths (overrun check)
Get-ChildItem "$audio\voice-native\*.mp3" | Sort-Object Name | ForEach-Object {
  $d = & ffprobe -v error -show_entries format=duration -of "csv=p=0" $_.FullName
  Write-Host ("    {0,-12} {1,6:N2}s" -f $_.BaseName, [double]$d)
}

Write-Host "=== [3/5] mix voice + BGM + SFX -> final-mix.wav ===" -ForegroundColor Cyan
& "$lib\mix_audio.ps1" -Voice $voiceover -Bgm $bgm -SfxDir $sfxDir -CueFile "$audio\sfx-cues.tsv" -Output $finalMix -Duration $Duration
if ($LASTEXITCODE -ne 0) { throw "mix_audio failed" }

Write-Host "=== [4/5] mux video + audio -> WITH-AUDIO.mp4 ===" -ForegroundColor Cyan
& "$lib\mux_video.ps1" -Video $silent -Audio $finalMix -Output $withAudio -Duration $Duration
if ($LASTEXITCODE -ne 0) { throw "mux_video failed" }

Write-Host "=== [5/5] verify ===" -ForegroundColor Cyan
& "$lib\verify_video.ps1" -Video $withAudio -Duration $Duration -Fps $Fps -Width $Width -Height $Height -Report $report
$verifyExit = $LASTEXITCODE

$sw.Stop()
Write-Host ("=== done in {0:N0}s ===" -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green
Get-Content $report
if ($verifyExit -ne 0) { Write-Host "VERIFICATION FAILED" -ForegroundColor Red; exit 1 }
Write-Host "OUTPUT: $withAudio" -ForegroundColor Green
