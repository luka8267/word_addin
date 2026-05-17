# Azure Static Web Apps

This folder contains the Word add-in static files and the Azure Functions API
used by the add-in.

Published URLs:

- `https://<your-app>.azurestaticapps.net/taskpane.html`
- `https://<your-app>.azurestaticapps.net/api/addin/papers?q=...`

## Folder layout

```text
azure-static-web-apps/
  README.md
  static/
    taskpane.html
    taskpane.js
    commands.html
    commands.js
    assets/
  api/
    host.json
    requirements.txt
    shared/
      bunken_service.py
      bunken_models.py
      data_access.py
    addin_auth_session/
      function.json
      __init__.py
    addin_papers/
      function.json
      __init__.py
    addin_citations_format/
      function.json
      __init__.py
    addin_bibliography_format/
      function.json
      __init__.py
    addin_documents_citations/
      function.json
      __init__.py
    addin_documents_sync/
      function.json
      __init__.py
```

## Local development

1. Copy `api/local.settings.json.example` to `api/local.settings.json`.
2. Put the same Supabase anon/publishable key used by the Streamlit app in
   `SUPABASE_PUBLISHABLE_KEY`.
3. Start the Functions API:

```powershell
cd api
func start --port 7071 --cors *
```

4. In a second terminal, start the Static Web Apps emulator:

```powershell
cd ..
npx -y @azure/static-web-apps-cli start ./static `
  --api-devserver-url http://localhost:7071 `
  --port 4280
```

5. Open `http://localhost:4280/taskpane.html`.

The taskpane and API are same-origin at `localhost:4280`; API requests are
proxied to the Functions host on `localhost:7071`.

Generate a local Word sideload manifest from the repository root:

```powershell
python bunkenn\generate_manifest.py --local
```

Use `bunkenn\manifest.local.xml` for the normal add-in and
`bunkenn\manifest.local.minimal.xml` for the first diagnostic check.

## Design notes

- Keep the add-in UI and API under the same Azure Static Web Apps origin.
- Use Azure Functions HTTP triggers for the API.
- Normal login, search, and sync calls use a Supabase anon/publishable key plus
  the user's access token. Do not use a service-role key for the add-in flow.

## Deployment

1. Create or reuse an Azure Static Web Apps resource.
2. Deploy `static/` as the app content.
3. Deploy `api/` as Azure Functions.
4. Generate the Office manifest with the published Static Web Apps URL.

## GitHub Actions

Use `github-actions-azure-static-web-apps.yml` as the deployment workflow
template when connecting Azure Static Web Apps to GitHub.
