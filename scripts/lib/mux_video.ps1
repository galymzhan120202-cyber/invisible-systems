param(
    [Parameter(Mandatory = $true)][string]$Video,
    [Parameter(Mandatory = $true)][string]$Audio,
    [string]$Output = 'final-WITH-AUDIO.mp4',
    [double]$Duration = 60.0
)

$ErrorActionPreference = 'Stop'
foreach ($required in @($Video, $Audio)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing input: $required" }
}

& ffmpeg -y -i $Video -i $Audio -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac `
    -profile:a aac_low -b:a 192k -ar 48000 -ac 2 -tag:a mp4a `
    -disposition:a:0 default -metadata:s:a:0 language=eng `
    -metadata:s:a:0 title='English narration, music, and sound effects' `
    -t $Duration -movflags +faststart $Output
if ($LASTEXITCODE -ne 0) { throw 'Video/audio mux failed.' }
Write-Host "Created $Output"
