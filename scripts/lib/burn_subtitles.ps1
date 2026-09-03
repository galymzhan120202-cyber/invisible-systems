param(
    [Parameter(Mandatory = $true)][string]$Video,
    [Parameter(Mandatory = $true)][string]$AssFile,
    [string]$Output = 'final-BILINGUAL-SUBTITLES.mp4'
)

$ErrorActionPreference = 'Stop'
foreach ($required in @($Video, $AssFile)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing input: $required" }
}

$assPath = [IO.Path]::GetFullPath($AssFile).Replace('\', '/').Replace(':', '\:')
& ffmpeg -y -i $Video -vf "ass='$assPath'" -map 0:v:0 -map 0:a:0 `
    -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p `
    -c:a copy -disposition:a:0 default -movflags +faststart $Output
if ($LASTEXITCODE -ne 0) { throw 'Subtitle burn failed.' }
Write-Host "Created $Output"
