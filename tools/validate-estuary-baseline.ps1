[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

Write-Host "Validation statique - baseline Estuary Omega / skin.dejaVu" -ForegroundColor Cyan

function Assert-File([string]$relative) {
    $path = Join-Path $repo $relative
    if (-not (Test-Path $path -PathType Leaf)) {
        throw "Fichier absent: $relative"
    }
}

function Assert-Directory([string]$relative) {
    $path = Join-Path $repo $relative
    if (-not (Test-Path $path -PathType Container)) {
        throw "Repertoire absent: $relative"
    }
}

# Manifest
Assert-File "addon.xml"
[xml]$addon = Get-Content (Join-Path $repo "addon.xml")
if ($addon.addon.id -ne "skin.dejavu") { throw "addon.xml: id inattendu: $($addon.addon.id)" }
if ($addon.addon.name -ne "dejaVu") { throw "addon.xml: name inattendu: $($addon.addon.name)" }

$gui = @($addon.addon.requires.import | Where-Object { $_.addon -eq "xbmc.gui" })
if (-not $gui -or $gui[0].version -ne "5.17.0") {
    throw "addon.xml: xbmc.gui doit etre 5.17.0"
}

$res = @($addon.addon.extension | Where-Object { $_.point -eq "xbmc.gui.skin" } | Select-Object -ExpandProperty res)
if (-not $res) { throw "addon.xml: aucune resolution de skin declaree" }
if (-not ($res | Where-Object { $_.width -eq "1920" -and $_.height -eq "1080" -and $_.default -eq "true" })) {
    throw "addon.xml: resolution 1920x1080 par defaut absente"
}
Write-Host "[OK] addon.xml / skin.dejavu / xbmc.gui 5.17.0"

# Estuary runtime directories
@(
    "xml",
    "fonts",
    "colors",
    "media",
    "language",
    "themes",
    "extras",
    "playlists",
    "resources"
) | ForEach-Object {
    Assert-Directory $_
    Write-Host "[OK] $_"
}

# Native Kodi surfaces from Estuary Omega
@(
    "xml\Home.xml",
    "xml\Includes.xml",
    "xml\Font.xml",
    "xml\Timers.xml",
    "xml\Settings.xml",
    "xml\SettingsCategory.xml",
    "xml\DialogSelect.xml",
    "xml\DialogConfirm.xml",
    "xml\DialogKeyboard.xml",
    "xml\DialogContextMenu.xml",
    "xml\DialogButtonMenu.xml",
    "xml\DialogBusy.xml",
    "xml\DialogNotification.xml",
    "xml\FileBrowser.xml",
    "xml\AddonBrowser.xml",
    "xml\PlayerControls.xml"
) | ForEach-Object {
    Assert-File $_
    Write-Host "[OK] $_"
}

# Baseline file-count checks
$xmlCount = @(Get-ChildItem (Join-Path $repo "xml") -File -Filter "*.xml").Count
if ($xmlCount -ne 104) {
    throw "xml/: nombre inattendu ($xmlCount, attendu 104 pour Estuary Omega)"
}
Write-Host "[OK] xml/ contient 104 fichiers XML"

$leftover = @(
    "resources\styles\tokens.xml",
    "resources\styles\screen_profiles.xml",
    "xml\Includes_SettingsDialog.xml"
)
foreach ($relative in $leftover) {
    if (Test-Path (Join-Path $repo $relative)) {
        throw "Fichier de l'ancien bootstrap encore present: $relative"
    }
}

# Our development layer is allowed and intentionally separate from Estuary.
Assert-File "DEV.md"
Assert-File "tools\install.ps1"
Assert-File "tools\reload.ps1"
Assert-File "tools\uninstall.ps1"
Write-Host "[OK] couche de developpement conservee"

Write-Host ""
Write-Host "Validation statique baseline Estuary Omega : OK" -ForegroundColor Green
Write-Host ""
Write-Host "Prochaine etape : validation reelle dans Kodi 21 (Home, navigation, dialogs, Settings, playback, changement de skin)." -ForegroundColor Yellow
