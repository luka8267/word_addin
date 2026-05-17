# word_addin

## Local Supabase API setup

Copy the example settings file and paste the same anon/publishable key used by
the Streamlit app:

```powershell
Copy-Item `
  bunkenn\azure-static-web-apps\api\local.settings.json.example `
  bunkenn\azure-static-web-apps\api\local.settings.json
```

Do not put a service-role key in `local.settings.json` unless you are doing a
server-only maintenance task. The add-in's normal login/search/sync flow should
use `SUPABASE_PUBLISHABLE_KEY`.

To run Azure Functions locally, install Azure Functions Core Tools, then run:

```powershell
cd bunkenn\azure-static-web-apps\api
func start
```

Smoke checks:

```powershell
Invoke-WebRequest `
  -Method POST `
  -Uri "http://localhost:7071/api/addin/auth/session?_debug=env" `
  -UseBasicParsing

Invoke-WebRequest `
  -Uri "http://localhost:7071/api/addin/papers?_debug=version" `
  -UseBasicParsing
```

`GET /api/addin/papers?q=` returns `401` until the add-in logs in and sends a
Supabase access token. A local `AzureWebJobsStorage` health warning can appear
when Azurite is not running; the HTTP endpoints above can still be used for
debugging.

## Local taskpane and API

For the closest local add-in check, run the API with Azure Functions and serve
the static taskpane through Azure Static Web Apps CLI:

```powershell
cd bunkenn\azure-static-web-apps\api
func start --port 7071 --cors *
```

In a second terminal:

```powershell
cd bunkenn\azure-static-web-apps
npx -y @azure/static-web-apps-cli start ./static `
  --api-devserver-url http://localhost:7071 `
  --port 4280
```

Open `http://localhost:4280/taskpane.html`. The taskpane will call
`http://localhost:4280/api/...`, and SWA CLI proxies those requests to the
local Functions host.

Generate local sideload manifests:

```powershell
python bunkenn\generate_manifest.py --local
```

This writes `bunkenn\manifest.local.xml` plus diagnostic variants such as
`manifest.local.minimal.xml`. These files point to `http://localhost:4280` and
are ignored by Git. Override the URL only when needed:

```powershell
$env:BUNKEN_LOCAL_BASE_URL="http://localhost:4280"
python bunkenn\generate_manifest.py --local
```

For Windows Word Desktop, use `bunkenn\manifest.local.xml` as the sideload
manifest after the local Functions host and SWA emulator are running. If Word
does not refresh after replacing the manifest, close Word and clear the Office
add-in cache before trying again.

With Node.js 24, `swa start ./static --api-location ./api` can fail because the
CLI rejects the Functions Core Tools/Node version combination. Use the
`--api-devserver-url` flow above unless you switch to a Functions-supported
Node LTS version.

## Test

```powershell
python -m pip install -r bunkenn\azure-static-web-apps\api\requirements.txt
python -m unittest discover -s tests -v
python -m py_compile `
  bunkenn\azure-static-web-apps\api\shared\data_access.py `
  bunkenn\azure-static-web-apps\api\shared\bunken_service.py `
  bunkenn\azure-static-web-apps\api\shared\bunken_models.py `
  bunkenn\azure-static-web-apps\api\addin_papers\__init__.py `
  bunkenn\azure-static-web-apps\api\addin_documents_sync\__init__.py
```
