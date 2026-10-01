param(
    [switch]$Commit,
    [switch]$Push
)

$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$gitDir = Join-Path $repo ".git"

if (-not (Test-Path $gitDir)) {
    throw "Ce script doit etre execute depuis le depot git skin.dejavu."
}

$branch = (git -C $repo branch --show-current).Trim()
if ($branch -ne "main") {
    throw "Le depot doit etre sur la branche main. Branche actuelle: $branch"
}

Write-Host "Synchronisation du depot avant migration..." -ForegroundColor Cyan
git -C $repo pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw "git pull --ff-only a echoue." }

$status = git -C $repo status --porcelain
if ($status) { throw "Le working tree doit etre propre avant migration. Execute git status puis nettoie les changements locaux." }

$sourceUrl = "https://github.com/xbmc/xbmc/archive/refs/heads/Omega.zip"
$tempRoot = Join-Path $env:TEMP ("skin-dejavu-estuary-omega-" + [guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $tempRoot "xbmc-omega.zip"
$extractPath = Join-Path $tempRoot "extract"

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    Write-Host "Telechargement d Estuary Omega..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $sourceUrl -OutFile $zipPath -UseBasicParsing
    Write-Host "Extraction..." -ForegroundColor Cyan
    Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

    $skinXml = Get-ChildItem -Path $extractPath -Recurse -File -Filter addon.xml |
        Where-Object { $_.FullName -match "[\\/]addons[\\/]skin\.estuary[\\/]addon\.xml$" } |
        Select-Object -First 1

    if (-not $skinXml) { throw "Impossible de trouver addons/skin.estuary/addon.xml dans l archive Omega." }

    $estuaryRoot = Split-Path $skinXml.FullName -Parent
    if (-not (Test-Path (Join-Path $estuaryRoot "xml"))) { throw "L archive Omega ne contient pas le repertoire xml attendu." }

    $migrationScript = Get-Content -LiteralPath $MyInvocation.MyCommand.Path -Raw

    Write-Host "Remplacement du contenu du depot par Estuary Omega..." -ForegroundColor Cyan
    Get-ChildItem -LiteralPath $repo -Force | Where-Object { $_.Name -ne ".git" } | Remove-Item -Recurse -Force
    Copy-Item -Path (Join-Path $estuaryRoot "*") -Destination $repo -Recurse -Force

    $addonPath = Join-Path $repo "addon.xml"
    [xml]$addonXml = Get-Content -LiteralPath $addonPath -Raw
    $addon = $addonXml.addon
    if (-not $addon) { throw "addon.xml invalide." }

    $addon.SetAttribute("id", "skin.dejavu")
    $addon.SetAttribute("version", "0.2.0")
    $addon.SetAttribute("name", "dejaVu")
    $addon.SetAttribute("provider-name", "dejaVu contributors; based on Estuary by phil65 and Piers")

    $sourceNode = $addon.extension | Where-Object { $_.point -eq "xbmc.addon.metadata" } | Select-Object -First 1
    if ($sourceNode.source) { $sourceNode.source = "https://github.com/doctornono/skin.dejavu" }

    $settings = New-Object System.Xml.XmlWriterSettings
    $settings.Indent = $true
    $settings.Encoding = New-Object System.Text.UTF8Encoding($false)
    $writer = [System.Xml.XmlWriter]::Create($addonPath, $settings)
    $addonXml.Save($writer)
    $writer.Dispose()

    New-Item -ItemType Directory -Path (Join-Path $repo "tools") -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $repo "tools\migrate-to-estuary-omega.ps1") -Value $migrationScript -Encoding UTF8

    @("# skin.dejaVu — Estuary Omega baseline","",
      "skin.dejaVu is now derived from the Kodi 21 Omega version of Estuary.","",
      "Source:","- Kodi repository: https://github.com/xbmc/xbmc","- Source path: addons/skin.estuary","- Branch: Omega","- Kodi GUI API: xbmc.gui 5.17.0","- Estuary version: 4.0.0","",
      "The complete Estuary runtime baseline is intentionally retained first: XML windows and includes; native dialogs; views; fonts; colors; media; languages; themes; playlists; resources.","",
      "The dejaVu experience will replace or extend this baseline progressively. Native Kodi compatibility remains the first constraint.","",
      "Estuary licensing and attribution are preserved in LICENSE.txt and addon.xml.") | Set-Content -LiteralPath (Join-Path $repo "DEJAVU_BASELINE.md") -Encoding UTF8

    @("# Development","",
      "The local Kodi installation uses a Windows junction directly to this repository:","",
      "C:\Users\conta\AppData\Roaming\Kodi\addons\skin.dejavu","->","D:\Developpement\dejavu-kodi-addons\skin.dejavu","",
      "The repository is therefore the active Kodi installation. Do not run an installer that copies or deletes this addon directory.","",
      "skin.dejavu is based on Estuary Omega / Kodi 21. Keep the native Estuary runtime intact until each replacement is validated.","",
      "Migration command:","powershell -ExecutionPolicy Bypass -File .\tools\migrate-to-estuary-omega.ps1 -Commit -Push") | Set-Content -LiteralPath (Join-Path $repo "DEV.md") -Encoding UTF8

    Write-Host "Migration Estuary Omega terminee." -ForegroundColor Green
    Write-Host "Version skin.dejavu: 0.2.0" -ForegroundColor Green
    Write-Host "xbmc.gui: 5.17.0" -ForegroundColor Green

    if ($Commit) {
        git -C $repo add -A
        if ($LASTEXITCODE -ne 0) { throw "git add a echoue." }
        git -C $repo commit -m "feat: reset skin.dejavu to Estuary Omega baseline"
        if ($LASTEXITCODE -ne 0) { throw "git commit a echoue." }
        if ($Push) {
            git -C $repo push origin main
            if ($LASTEXITCODE -ne 0) { throw "git push a echoue." }
            Write-Host "Migration poussee sur origin/main." -ForegroundColor Green
        }
    } else {
        Write-Host "Aucun commit automatique. Execute avec -Commit pour creer le commit." -ForegroundColor Yellow
    }
} finally {
    if (Test-Path $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue }
}