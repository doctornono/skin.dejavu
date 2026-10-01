[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$required = @(
  "addon.xml",
  "xml\Home.xml",
  "xml\Includes.xml",
  "xml\Font.xml",
  "xml\Timers.xml",
  "xml\Defaults.xml",
  "xml\Startup.xml",
  "xml\DialogBusy.xml",
  "xml\Pointer.xml",
  "xml\DialogVolumeBar.xml",
  "xml\DialogExtendedProgressBar.xml",
  "xml\DialogSeekBar.xml",
  "xml\DialogNotification.xml",
  "xml\AddonBrowser.xml",
  "resources\styles\tokens.xml",
  "resources\styles\screen_profiles.xml",
  "tools\install.ps1",
  "tools\reload.ps1",
  "tools\uninstall.ps1"
)
Write-Host "Lot 1 - validation statique skin.dejaVu"
foreach ($relative in $required) {
  $path = Join-Path $repo $relative
  if (-not (Test-Path $path -PathType Leaf)) { throw "Fichier requis absent: $relative" }
  Write-Host "[OK] $relative"
}
[xml]$addon = Get-Content (Join-Path $repo "addon.xml")
if ($addon.addon.id -ne "skin.dejavu") { throw "addon.xml: id inattendu" }
$gui = @($addon.addon.requires.import | Where-Object { $_.addon -eq "xbmc.gui" })
if (-not $gui -or $gui[0].version -ne "5.17.0") { throw "addon.xml: compatibilite xbmc.gui inattendue" }
Write-Host "[OK] addon.xml / skin.dejavu / xbmc.gui 5.17.0"
$includes = Get-Content (Join-Path $repo "xml\Includes.xml") -Raw
foreach ($include in @("tokens.xml", "screen_profiles.xml", "Defaults.xml")) {
  if ($includes -notmatch [regex]::Escape($include)) { throw "xml/Includes.xml: $include n'est pas inclus" }
}
Write-Host "[OK] Includes.xml bootstrap"
[xml]$tokens = Get-Content (Join-Path $repo "resources\styles\tokens.xml")
[xml]$profiles = Get-Content (Join-Path $repo "resources\styles\screen_profiles.xml")
[xml]$font = Get-Content (Join-Path $repo "xml\Font.xml")
[xml]$home = Get-Content (Join-Path $repo "xml\Home.xml")
if (-not $tokens.includes.constant) { throw "tokens.xml invalide" }
if (-not $profiles.includes.constant) { throw "screen_profiles.xml invalide" }
if (-not $font.fonts.fontset) { throw "Font.xml invalide" }
if (-not $home.window.controls) { throw "Home.xml invalide" }
Write-Host "[OK] XML tokens/profils/font/home parse"
Write-Host ""
Write-Host "Validation statique Lot 1: OK"
Write-Host "Prochaine etape: installer dans Kodi 21 puis executer la matrice de validation Kodi."
