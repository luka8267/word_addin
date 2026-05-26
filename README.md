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
- `chrome_extension`: Chrome / Brave MV3 extension for saving paper pages to bunken.

## Chrome Extension

The extension is distributed as a ZIP from the bunken app sidebar. It uses the
production API URL baked into `chrome_extension\popup.js` and authenticates with
the same Supabase account as bunken.

Local install / update:

1. Download the ZIP from the bunken sidebar.
2. Extract the ZIP.
3. Open `chrome://extensions` or `brave://extensions`.
4. Enable developer mode.
5. Remove the old `bunken Web Importer` extension if it is already installed.
6. Choose `Load unpacked` and select the extracted `bunken-web-importer` folder.
7. Log in once. The extension stores a refresh token, not the password.

Smoke test:

1. Open a paper landing page with citation metadata, DOI, or PDF links.
2. Open the extension popup.
3. Confirm title, DOI, and PDF candidate count are shown.
4. Click `bunken に保存`.
5. Confirm the popup reports either `bunken に保存しました。` or `すでに bunken に登録されています。`.
6. Open bunken and confirm the saved paper appears near the latest imported records.
7. If a PDF was saved, confirm the paper has a PDF attachment. If the publisher blocks API PDF fetching, use `PDF候補を開く` and upload manually from bunken.

API smoke test with a real authenticated user:

```powershell
$env:BUNKEN_EXTENSION_ACCESS_TOKEN="<Supabase access token>"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Smoke-ExtensionSave.ps1
```

This creates one smoke-test paper, posts the same DOI again to verify duplicate
handling, searches it through `/api/addin/papers`, and attempts to save a small
public PDF candidate to Storage. Use a test account when possible.

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
python -m json.tool chrome_extension\manifest.json
node --check chrome_extension\popup.js
node tests\test_chrome_extension.js
python -m py_compile `
  api\_bunken_vercel.py `
  bunkenn\word-app\api\shared\data_access.py `
  bunkenn\word-app\api\shared\bunken_service.py `
  bunkenn\word-app\api\shared\bunken_models.py
node --check bunkenn\word-app\static\taskpane.js
npm run build
```

## Production checklist

Before release:

- confirm Vercel env vars: `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`
- keep `BUNKEN_ENABLE_DEBUG_ENDPOINTS=false` unless actively debugging
- run the test commands above
- generate a production manifest only when the public URL changed
- clear Word add-in cache after replacing a local manifest

After release:

```powershell
curl.exe -L "https://word-addin-sooty.vercel.app/taskpane.html"
curl.exe -L "https://word-addin-sooty.vercel.app/api/addin/papers?_debug=version"
curl.exe -i -X POST "https://word-addin-sooty.vercel.app/api/addin/extension/save" -H "Content-Type: application/json" -H "Origin: chrome-extension://test" -d "{}"
```

Then smoke-test login, search, citation insertion, bibliography update, style
switching, and document citation sync in Word.
