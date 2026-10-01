[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

Write-Host "Validation visuelle initiale skin.dejaVu" -ForegroundColor Cyan

$addonFile = Join-Path $repo "addon.xml"
$homeFile = Join-Path $repo "xml\Home.xml"
$colorsFile = Join-Path $repo "colors\defaults.xml"

foreach ($path in @($addonFile,$homeFile,$colorsFile)) {
    if (-not (Test-Path $path -PathType Leaf)) {
        throw "Fichier absent: $path"
    }
}

[xml]$addonXml = Get-Content $addonFile
[xml]$homeXml = Get-Content $homeFile
[xml]$colorsXml = Get-Content $colorsFile

if ($addonXml.addon.id -ne "skin.dejavu") { throw "addon.xml invalide: id" }
if ($addonXml.addon.name -ne "dejaVu") { throw "addon.xml invalide: name" }

$requiredColors = @{
    "button_focus" = "FF7B2820"
    "background"   = "FF101010"
    "selected"     = "FFD9A441"
}

foreach ($name in $requiredColors.Keys) {
    $node = @($colorsXml.colors.color | Where-Object { $_.name -eq $name }) | Select-Object -First 1
    if (-not $node) { throw "Couleur manquante: $name" }
    if ($node.'#text' -ne $requiredColors[$name]) { throw "Couleur inattendue: $name = $($node.'#text')" }
}

$homeText = Get-Content $homeFile -Raw
if ($homeText -notmatch "Votre espace de lecture") {
    throw "Chrome dejaVu absent de Home.xml"
}
if ($homeText -notmatch 'colordiffuse="button_focus"') {
    throw "Accent visuel dejaVu absent de Home.xml"
}
if (-not $homeXml.window.controls) {
    throw "Home.xml invalide"
}

Write-Host "[OK] addon.xml"
Write-Host "[OK] palette burgundy/dark"
Write-Host "[OK] chrome visuel Home"
Write-Host ""
Write-Host "Validation visuelle initiale : OK" -ForegroundColor Green
Write-Host "Prochaine etape : validation visuelle Kodi 21 puis iteration Home dejaVu."
