[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"

$repo = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$kodiHome = if ($env:KODI_HOME) { $env:KODI_HOME } else { Join-Path $env:APPDATA "Kodi" }
$target = Join-Path $kodiHome "addons\skin.dejavu"

if (-not (Test-Path (Join-Path $repo "addon.xml"))) {
  throw "addon.xml introuvable dans $repo"
}

# skin.dejaVu is developed through a Kodi junction. In that mode the repository
# IS the Kodi addon directory: never copy, clean, or delete it.
$targetItem = Get-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue
if ($targetItem -and ($targetItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
  $targetResolved = $null
  try { $targetResolved = (Resolve-Path -LiteralPath $target).Path } catch {}
  if ($targetResolved -eq $repo) {
    Write-Host "Mode developpement: Kodi pointe directement vers le depot $repo"
    Write-Host "Aucune copie ni suppression effectuee."
    Write-Host "Mise a jour Kodi: git pull dans le depot, puis rechargement de la skin."
    exit 0
  }

  throw "SECURITE: $target est un lien/junction. Installation refusee pour eviter toute suppression indirecte."
}

# A real development checkout must never be treated as an installation target.
if (Test-Path (Join-Path $target ".git")) {
  throw "SECURITE: $target contient .git. Installation annulee; aucun fichier n'a ete supprime."
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
