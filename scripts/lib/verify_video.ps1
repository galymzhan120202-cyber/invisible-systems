param(
    [Parameter(Mandatory = $true)][string]$Video,
    [double]$Duration = 60.0,
    [int]$Fps = 24,
    [int]$Width = 1080,
    [int]$Height = 1920,
    [string]$Report = 'verification-report.md'
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Video)) { throw "Missing video: $Video" }

$probe = ffprobe -v error -count_frames -show_entries `
    format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,nb_read_frames:stream_disposition=default `
    -of json $Video | ConvertFrom-Json
$videoStream = $probe.streams | Where-Object codec_type -eq 'video' | Select-Object -First 1
$audioStream = $probe.streams | Where-Object codec_type -eq 'audio' | Select-Object -First 1
$errors = [Collections.Generic.List[string]]::new()

if (-not $videoStream) { $errors.Add('Missing video stream') }
if (-not $audioStream) { $errors.Add('Missing audio stream') }
if ($videoStream.codec_name -ne 'h264') { $errors.Add("Expected H.264, found $($videoStream.codec_name)") }
if ($videoStream.width -ne $Width -or $videoStream.height -ne $Height) { $errors.Add('Resolution mismatch') }
$fpsParts = $videoStream.r_frame_rate -split '/'
$actualFps = [double]$fpsParts[0] / [double]$fpsParts[1]
if ([Math]::Abs($actualFps - $Fps) -gt 0.01) { $errors.Add("FPS mismatch: $actualFps") }
$actualDuration = [double]$probe.format.duration
if ([Math]::Abs($actualDuration - $Duration) / $Duration -gt 0.02) { $errors.Add("Duration mismatch: $actualDuration") }
if ($audioStream -and $audioStream.codec_name -ne 'aac') { $errors.Add("Expected AAC, found $($audioStream.codec_name)") }
if ($audioStream -and $audioStream.disposition.default -ne 1) { $errors.Add('Audio stream is not default') }

$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
# Dark-theme aware: a minimalist black-canvas animation is mostly black by design,
# so blackdetect (frame is >=98% black) would false-positive on every frame.
# Instead flag only frames that are *entirely* empty (100% of pixels below luma 24) -
# i.e. the animation genuinely drew nothing. Any visible line/dot/colour clears it.
$blackLog = & ffmpeg -hide_banner -i $Video -vf 'blackframe=amount=100:threshold=24' -an -f null NUL 2>&1
$blackHits = $blackLog | Select-String 'Parsed_blackframe'
if ($blackHits -and $blackHits.Count -ge 3) { $errors.Add("Detected $($blackHits.Count) empty (nothing-drawn) frames") }

$loudLog = & ffmpeg -hide_banner -i $Video -filter_complex 'ebur128=peak=true' -f null NUL 2>&1
$ErrorActionPreference = $previousErrorAction
$integratedLine = ($loudLog | Select-String 'I:' | Select-Object -Last 1).Line
$peakLine = ($loudLog | Select-String 'Peak:' | Select-Object -Last 1).Line
$integrated = if ($integratedLine -match 'I:\s+(-?[0-9.]+)') { [double]$Matches[1] } else { $null }
$peak = if ($peakLine -match 'Peak:\s+(-?[0-9.]+)') { [double]$Matches[1] } else { $null }
if ($null -eq $integrated -or $integrated -lt -18 -or $integrated -gt -10) { $errors.Add("Loudness outside -14 +/- 4 LUFS: $integrated") }
if ($null -eq $peak -or $peak -gt -1.0) { $errors.Add("True peak is too high: $peak") }

$status = if ($errors.Count -eq 0) { 'PASS' } else { 'FAIL' }
$lines = @(
    '# Video Verification', '',
    "- Status: **$status**",
    "- Artifact: ``$([IO.Path]::GetFileName($Video))``",
    "- Duration: $actualDuration seconds",
    "- Resolution: $($videoStream.width) x $($videoStream.height)",
    "- Frame rate: $actualFps FPS",
    "- Frame count: $($videoStream.nb_read_frames)",
    "- Video codec: $($videoStream.codec_name)",
    "- Audio codec: $($audioStream.codec_name)",
    "- Audio default: $($audioStream.disposition.default)",
    "- Integrated loudness: $integrated LUFS",
    "- True peak: $peak dBFS",
    "- Black segments: $($blackHits.Count)",
    '', '## Errors', ''
)
if ($errors.Count -eq 0) { $lines += '- None' } else { $lines += $errors | ForEach-Object { "- $_" } }
Set-Content -LiteralPath $Report -Value $lines -Encoding UTF8
Write-Host "$status - report written to $Report"
if ($errors.Count -gt 0) { exit 1 }
