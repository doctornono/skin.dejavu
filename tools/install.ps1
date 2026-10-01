[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$kodiHome = if ($env:KODI_HOME) { $env:KODI_HOME } else { Join-Path $env:APPDATA "Kodi" }
$target = Join-Path $kodiHome "addons\skin.dejavu"
if (-not (Test-Path (Join-Path $repo "addon.xml"))) { throw "addon.xml introuvable dans $repo" }
New-Item -ItemType Directory -Force -Path $target | Out-Null
Get-ChildItem -Path $repo -Force | Where-Object { $_.Name -notin @(".git", ".github") } | ForEach-Object {
  Copy-Item -Path $_.FullName -Destination $target -Recurse -Force
}
Write-Host "skin.dejavu installee dans: $target"
