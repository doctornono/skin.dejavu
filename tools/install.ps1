[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$kodiHome = if ($env:KODI_HOME) { $env:KODI_HOME } else { Join-Path $env:APPDATA "Kodi" }
$target = Join-Path $kodiHome "addons\skin.dejavu"

if (-not (Test-Path (Join-Path $repo "addon.xml"))) {
  throw "addon.xml introuvable dans $repo"
}

if (-not (Test-Path $target)) {
  New-Item -ItemType Directory -Force -Path $target | Out-Null
}
else {
  Write-Host "Nettoyage de l'installation precedente: $target"
  Get-ChildItem -Path $target -Force | Remove-Item -Recurse -Force
}

Get-ChildItem -Path $repo -Force |
  Where-Object { $_.Name -notin @(".git", ".github") } |
  ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $target -Recurse -Force
  }

Write-Host "skin.dejavu installee dans: $target"
