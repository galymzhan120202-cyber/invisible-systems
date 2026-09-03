param(
    [Parameter(Mandatory = $true)][string]$Voice,
    [Parameter(Mandatory = $true)][string]$Bgm,
    [Parameter(Mandatory = $true)][string]$SfxDir,
    [Parameter(Mandatory = $true)][string]$CueFile,
    [string]$Output = 'final-mix.wav',
    [double]$Duration = 60.0,
    [double]$BgmGain = 0.12
)

$ErrorActionPreference = 'Stop'
foreach ($required in @($Voice, $Bgm, $SfxDir, $CueFile)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing input: $required" }
}

$outputPath = [IO.Path]::GetFullPath($Output)
$outputDir = Split-Path -Parent $outputPath
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
$sfxTrack = Join-Path $outputDir 'sfx-track.wav'
$cues = Import-Csv -LiteralPath $CueFile -Delimiter "`t"
if (-not $cues) { throw 'The SFX cue file is empty.' }

$args = @('-y')
foreach ($cue in $cues) {
    $asset = Join-Path $SfxDir $cue.asset
    if (-not (Test-Path -LiteralPath $asset)) { throw "Missing SFX: $asset" }
    $args += @('-i', $asset)
}

$filters = @()
$labels = @()
for ($i = 0; $i -lt $cues.Count; $i++) {
    $delay = [int][Math]::Round(([double]$cues[$i].time) * 1000)
    $gain = [double]$cues[$i].gain
    $label = "s$i"
    $filters += "[$i`:a]aformat=sample_rates=48000:channel_layouts=stereo,highpass=f=800,volume=$gain,adelay=$delay|$delay[$label]"
    $labels += "[$label]"
}
$filters += (($labels -join '') + "amix=inputs=$($cues.Count):duration=longest:normalize=0,apad=whole_dur=$Duration,atrim=0:$Duration[sfx]")
$args += @('-filter_complex', ($filters -join ';'), '-map', '[sfx]', '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', '-t', "$Duration", $sfxTrack)
& ffmpeg @args
if ($LASTEXITCODE -ne 0) { throw 'SFX render failed.' }

$fadeOut = $Duration - 1.5
$mix = "[0:a]aformat=sample_rates=48000:channel_layouts=stereo,apad=whole_dur=$Duration,atrim=0:$Duration[voice];" +
       "[1:a]atrim=0:$Duration,aformat=sample_rates=48000:channel_layouts=stereo,afade=in:st=0:d=0.3,afade=out:st=$fadeOut`:d=1.5,lowpass=f=4000,volume=$BgmGain[bgm];" +
       "[2:a]aformat=sample_rates=48000:channel_layouts=stereo[sfx];" +
       "[voice][bgm][sfx]amix=inputs=3:duration=longest:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=8,atrim=0:$Duration[mix]"

& ffmpeg -y -i $Voice -stream_loop -1 -i $Bgm -i $sfxTrack -filter_complex $mix `
    -map '[mix]' -ar 48000 -ac 2 -c:a pcm_s24le -t $Duration $outputPath
if ($LASTEXITCODE -ne 0) { throw 'Final audio mix failed.' }
Write-Host "Created $outputPath"
