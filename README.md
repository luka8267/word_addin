# word_addin

Word citation add-in for bunken. The production task pane and API are deployed
on Vercel.

## Deployment

- [Deployment without localhost](docs/DEPLOYMENT.md)

## App Layout

- `bunkenn\word-app\static`: Word task pane static files.
- `bunkenn\word-app\api\shared`: shared API logic used by Vercel handlers.
- `api\addin\*`: Vercel Python API entry points.
- `public`: generated static output for Vercel.

## Local Taskpane and API

Build the static task pane into `public`:

```powershell
npm run build
```

Run Vercel locally when you want the task pane and API on one origin:

```powershell
npx vercel dev
```

Then open the local URL shown by Vercel, usually:

```text
http://localhost:3000/taskpane.html
```

Generate local sideload manifests:

```powershell
python bunkenn\generate_manifest.py --local
```

This writes `bunkenn\manifest.local.xml` plus diagnostic variants such as
`manifest.local.minimal.xml`. These files point to `http://localhost:4280` by
default and are ignored by Git. Override the URL when needed:

```powershell
$env:BUNKEN_LOCAL_BASE_URL="http://localhost:3000"
python bunkenn\generate_manifest.py --local
```

For Windows Word Desktop, use `bunkenn\manifest.local.xml` as the sideload
manifest after the local Vercel-compatible server is running. If Word does not
refresh after replacing the manifest, close Word and clear the Office add-in
cache before trying again.

To prepare a Windows shared-folder catalog copy:

```powershell
.\scripts\Prepare-LocalWordSideload.ps1 -BaseUrl "http://localhost:3000" -CheckLocalServer
```

This generates the local manifest and copies it to
`%USERPROFILE%\Documents\bunken-word-addin-catalog\manifest.xml`. Windows Word
loads test add-ins from a trusted shared-folder catalog, so either share that
folder manually or run PowerShell as Administrator with `-CreateShare`:

```powershell
.\scripts\Prepare-LocalWordSideload.ps1 -BaseUrl "http://localhost:3000" -CheckLocalServer -CreateShare
```

If Word keeps showing an old taskpane or 404 after the manifest changes, close
Word and clear the local add-in cache:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Clear-WordAddinCache.ps1
```

If Word or WebView processes are stuck, rerun with `-CloseWord`.

Then add the network share, for example `\\localhost\bunken-word-addin-catalog`,
under Word's trusted add-in catalogs, restart Word, and open the add-in from
`Insert > My Add-ins > Shared Folder`.

Reference: [Microsoft Learn - Sideload Office Add-ins from a network share](https://learn.microsoft.com/en-us/office/dev/add-ins/testing/create-a-network-shared-folder-catalog-for-task-pane-and-content-add-ins).

## Test

```powershell
python -m unittest discover -s tests -v
python -m py_compile `
  api\_bunken_vercel.py `
  bunkenn\word-app\api\shared\data_access.py `
  bunkenn\word-app\api\shared\bunken_service.py `
  bunkenn\word-app\api\shared\bunken_models.py
node --check bunkenn\word-app\static\taskpane.js
npm run build
```
