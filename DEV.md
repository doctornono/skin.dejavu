# skin.dejaVu — développement local

Le test local ne nécessite aucune publication.

Pré-requis :
- Kodi 21 Omega
- PowerShell 5.1+ ou PowerShell 7
- dépôt cloné localement

Installation : .\tools\install.ps1

Par défaut, le script utilise %APPDATA%\Kodi. Pour un autre profil Kodi, définir KODI_HOME avant l'installation.

La skin est copiée vers <KODI_HOME>\addons\skin.dejavu.

Rechargement : .\tools\reload.ps1

Le rechargement automatique utilise JSON-RPC si le contrôle HTTP de Kodi est activé. Sinon, recharge manuellement la skin dans Kodi avec ReloadSkin().

Variables optionnelles : KODI_JSONRPC_URL, KODI_USER, KODI_PASSWORD.

Désinstallation : .\tools\uninstall.ps1

La suppression cible exclusivement addons\skin.dejavu.

Règle : modifier le dépôt, installer localement, recharger Kodi, puis valider dans Kodi 21. Aucun dépôt distant ou publication n'est nécessaire pendant le développement.
