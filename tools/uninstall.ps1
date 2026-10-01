[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$kodiHome = if ($env:KODI_HOME) { $env:KODI_HOME } else { Join-Path $env:APPDATA "Kodi" }
$target = Join-Path $kodiHome "addons\skin.dejavu"
if (Test-Path $target) { Remove-Item -Path $target -Recurse -Force; Write-Host "skin.dejavu supprimee de: $target" }
else { Write-Host "skin.dejavu n'est pas installee." }
