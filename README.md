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
