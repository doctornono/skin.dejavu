[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"

$kodiHome = if ($env:KODI_HOME) { $env:KODI_HOME } else { Join-Path $env:APPDATA "Kodi" }
$target = Join-Path $kodiHome "addons\skin.dejavu"

if (-not (Test-Path $target)) {
  Write-Host "skin.dejavu n'est pas installee."
  exit 0
}

$item = Get-Item -LiteralPath $target -Force
if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
  throw "SECURITE: $target est une junction/symlink. Desinstallation refusee pour proteger le depot de developpement."
}

if (Test-Path (Join-Path $target ".git")) {
  throw "SECURITE: $target contient .git. Desinstallation refusee pour proteger le depot de developpement."
}

Remove-Item -LiteralPath $target -Recurse -Force
Write-Host "skin.dejavu supprimee de: $target"
