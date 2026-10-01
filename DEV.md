# skin.dejaVu — développement local

## Mode développement Kodi recommandé

Le dépôt de développement est directement utilisé par Kodi via une **junction Windows** :

`%APPDATA%\Kodi\addons\skin.dejavu` → dépôt `skin.dejavu`.

Dans ce mode, **le dépôt est déjà l'installation Kodi**. Il ne faut donc jamais copier, nettoyer ou supprimer son contenu avec un script.

### Workflow

Après une modification locale :

```powershell
git status
git add .
git commit -m "..."
git push
```

Pour récupérer une modification distante :

```powershell
git pull
```

Kodi utilise alors immédiatement les fichiers du dépôt. Un rechargement de la skin ou un redémarrage de Kodi peut être nécessaire pour prendre en compte les XML déjà chargés.

### Installation / désinstallation

`tools/install.ps1` et `tools/uninstall.ps1` restent présents pour des installations **hors dépôt de développement**, mais ils refusent toute opération destructive lorsqu'ils détectent une junction/symlink ou un dépôt Git.

**Ne jamais utiliser ces scripts pour supprimer ou réinstaller le dépôt de développement.**

### Rechargement

`tools/reload.ps1`

Le rechargement automatique utilise JSON-RPC si le contrôle HTTP de Kodi est activé. Sinon, recharger manuellement la skin dans Kodi avec `ReloadSkin()`.

Variables optionnelles : `KODI_JSONRPC_URL`, `KODI_USER`, `KODI_PASSWORD`.

### Pré-requis

- Kodi 21 Omega
- PowerShell 5.1+ ou PowerShell 7
- dépôt cloné localement
- junction Kodi pointant vers le dépôt pour le développement recommandé

## Règle d'implémentation — Estuary d'abord

skin.dejaVu est construit **au-dessus du runtime et des composants Estuary Omega**.

Avant de créer un composant ou un comportement propre à dejaVu, vérifier d'abord si Estuary fournit déjà une primitive adaptée (include, bouton, liste, panel, layout, navigation/focus, dialogue, carte ou autre composant réutilisable).

Ordre obligatoire :
1. réutiliser le composant Estuary existant ;
2. le paramétrer avec le contenu/comportement dejaVu ;
3. n'ajouter une abstraction dejaVu que si aucun composant Estuary approprié n'existe ;
4. affiner ensuite l'aspect visuel et le contenu sans remplacer inutilement le comportement Kodi validé.

La priorité est donc **comportement Estuary → contenu dejaVu → aspect visuel dejaVu**.
