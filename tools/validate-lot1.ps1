[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$required = @(
  "addon.xml",
  "xml\Includes.xml",
  "resources\styles\tokens.xml",
  "resources\styles\screen_profiles.xml",
  "tools\install.ps1",
  "tools\reload.ps1",
  "tools\uninstall.ps1"
)

Write-Host "Lot 1 - validation statique skin.dejaVu"

foreach ($relative in $required) {
  $path = Join-Path $repo $relative
  if (-not (Test-Path $path -PathType Leaf)) {
    throw "Fichier requis absent: $relative"
  }
  Write-Host "[OK] $relative"
}

[xml]$addon = Get-Content (Join-Path $repo "addon.xml")
if ($addon.addon.id -ne "skin.dejavu") { throw "addon.xml: id inattendu" }
if ($addon.addon.requires.import | Where-Object { $_.addon -eq "xbmc.gui" -and $_.version -ne "5.17.0" }) {
  throw "addon.xml: compatibilite xbmc.gui inattendue"
}
Write-Host "[OK] addon.xml / skin.dejavu / xbmc.gui 5.17.0"

$includes = Get-Content (Join-Path $repo "xml\Includes.xml") -Raw
foreach ($include in @("tokens.xml", "screen_profiles.xml")) {
  if ($includes -notmatch [regex]::Escape($include)) {
    throw "xml/Includes.xml: $include n'est pas inclus"
  }
}
Write-Host "[OK] tokens + screen profiles charges par Includes.xml"

[xml]$tokens = Get-Content (Join-Path $repo "resources\styles\tokens.xml")
[xml]$profiles = Get-Content (Join-Path $repo "resources\styles\screen_profiles.xml")
if (-not $tokens.includes.constant) { throw "tokens.xml vide ou invalide" }
if (-not $profiles.includes.constant) { throw "screen_profiles.xml vide ou invalide" }
Write-Host "[OK] XML tokens/profils parse"

Write-Host ""
Write-Host "Validation statique Lot 1: OK"
Write-Host "Prochaine etape: installer dans Kodi 21 puis executer la matrice de validation Kodi."
