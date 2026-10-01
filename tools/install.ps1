[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"

$repo = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$kodiHome = if ($env:KODI_HOME) { $env:KODI_HOME } else { Join-Path $env:APPDATA "Kodi" }
$target = Join-Path $kodiHome "addons\skin.dejavu"

if (-not (Test-Path (Join-Path $repo "addon.xml"))) {
  throw "addon.xml introuvable dans $repo"
}

# Development mode: Kodi may point directly (or through a junction/symlink)
# to this repository. Never delete or copy into the development tree.
$targetResolved = $null
if (Test-Path $target) {
  try {
    $targetResolved = (Resolve-Path -LiteralPath $target).Path
  }
  catch {
    $targetResolved = $null
  }
}

if ($targetResolved -and $targetResolved -eq $repo) {
  Write-Host "Mode developpement detecte: Kodi utilise directement le depot $repo"
  Write-Host "Aucune copie ni suppression effectuee."
  Write-Host "Pour mettre a jour Kodi, utilisez simplement git pull dans le depot."
  exit 0
}

# Safety guard: a real development repository contains .git.
# Refuse to delete it even if the Kodi path is linked through a junction.
if (Test-Path (Join-Path $target ".git")) {
  throw "SECURITE: $target semble etre le depot de developpement (presence de .git). Installation annulee; aucun fichier n'a ete supprime."
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
