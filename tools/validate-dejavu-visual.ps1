[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

Write-Host "Validation de la page de test dejaVu" -ForegroundColor Cyan

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
if ($homeText -notmatch "Accueil dejaVu - tests") {
    throw "Entrée Accueil dejaVu - tests absente du menu gauche"
}
if ($homeText -notmatch 'Skin.HasSetting\(dejavu_test_home\)') {
    throw "Bascule de la page de test absente de Home.xml"
}
if ($homeText -notmatch 'id="22001"') {
    throw "Contrôle de test du focus absent de Home.xml"
}
if ($homeText -match "Votre espace de lecture|dejaVu navigation chrome") {
    throw "L'habillage graphique provisoire doit rester désactivé"
}
if (-not $homeXml.window.controls) {
    throw "Home.xml invalide"
}

Write-Host "[OK] addon.xml"
Write-Host "[OK] palette burgundy/dark"
Write-Host "[OK] menu gauche vers la page de test"
Write-Host "[OK] page de test et contrôles de focus/actions"
Write-Host "[OK] habillage graphique provisoire retiré"
Write-Host ""
Write-Host "Validation de la page de test : OK" -ForegroundColor Green
Write-Host "Prochaine étape : tester le menu gauche et les contrôles dans Kodi 21."
