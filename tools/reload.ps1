[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$url = if ($env:KODI_JSONRPC_URL) { $env:KODI_JSONRPC_URL } else { "http://127.0.0.1:8080/jsonrpc" }
$body = @{ jsonrpc="2.0"; method="Input.ExecuteAction"; params=@{ action="reloadskin" }; id=1 } | ConvertTo-Json -Depth 5
$headers = @{}
if ($env:KODI_USER -or $env:KODI_PASSWORD) {
  $pair = "{0}:{1}" -f $env:KODI_USER, $env:KODI_PASSWORD
  $bytes = [Text.Encoding]::ASCII.GetBytes($pair)
  $headers.Authorization = "Basic " + [Convert]::ToBase64String($bytes)
}
try {
  $response = Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json" -Headers $headers -Body $body
  if ($response.error) { throw $response.error.message }
  Write-Host "Demande de rechargement envoyee a Kodi."
} catch {
  Write-Warning "Rechargement JSON-RPC impossible: $($_.Exception.Message)"
  Write-Host "Recharge manuellement la skin dans Kodi avec ReloadSkin()."
}
