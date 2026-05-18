# Deployment

## Recommended Free Host

Use Vercel Hobby when Azure is unavailable. Vercel can serve the static task pane
and Python API from the same origin.

Vercel files in this repo:

- `vercel.json`
- `api/addin/[...path].py`
- `requirements.txt`

## Goal

Run `bunken Word` without localhost by hosting the task pane and API on Azure
Static Web Apps.

Production URL currently used by the manifest:

```text
https://jolly-smoke-0e8ae9a10.7.azurestaticapps.net
```

## GitHub Actions

The active workflow is:

```text
.github/workflows/azure-static-web-apps-jolly-smoke-0e8ae9a10.yml
```

It deploys:

- Static app: `bunkenn/azure-static-web-apps/static`
- API: `bunkenn/azure-static-web-apps/api`

Required GitHub secret:

```text
AZURE_STATIC_WEB_APPS_API_TOKEN_JOLLY_SMOKE_0E8AE9A10
```

If this secret is missing or expired, GitHub can push successfully but Azure
will not deploy the latest files. A stale deployment often appears as a 404 for
`/taskpane.html`.

## Azure Static Web Apps Environment Variables

Set these in Azure Portal > Static Web App > Environment variables:

```text
SUPABASE_URL=https://udhgdndfcmdgpnxpksvo.supabase.co
SUPABASE_PUBLISHABLE_KEY=<Supabase anon or publishable key>
```

Optional:

```text
BUNKEN_DEFAULT_USERNAME=cloud-user
BUNKEN_DEFAULT_EMAIL=
```

Do not expose a Supabase service-role key unless doing a server-only maintenance
task. Normal login/search/sync uses the user's Supabase access token plus the
publishable key.

## Smoke Checks

After GitHub Actions deploys, check:

```powershell
curl.exe -L https://jolly-smoke-0e8ae9a10.7.azurestaticapps.net/taskpane.html
curl.exe -L "https://jolly-smoke-0e8ae9a10.7.azurestaticapps.net/api/addin/papers?_debug=version"
```

Expected API version:

```json
{"version":"citation-context-sync-v1"}
```

## Word Add-in Manifest

Use:

```text
bunkenn/manifest.production.xml
```

This manifest points Word to the Azure Static Web Apps URL, so Word no longer
needs the local Functions host or SWA CLI.

## Vercel Deployment

1. Import `luka8267/word_addin` into Vercel.
2. Use the repository root as the Vercel project root.
3. Keep the framework preset as `Other`.
4. Set environment variables:

```text
SUPABASE_URL=https://udhgdndfcmdgpnxpksvo.supabase.co
SUPABASE_PUBLISHABLE_KEY=<Supabase anon or publishable key>
```

Optional debug variable:

```text
BUNKEN_ENABLE_DEBUG_ENDPOINTS=true
```

5. Deploy the `main` branch.
6. Check:

```powershell
curl.exe -L https://<your-vercel-app>.vercel.app/taskpane.html
curl.exe -L "https://<your-vercel-app>.vercel.app/api/addin/papers?_debug=version"
```

7. Generate a production manifest for the Vercel URL:

```powershell
$env:BUNKEN_PUBLIC_BASE_URL="https://<your-vercel-app>.vercel.app"
python bunkenn\generate_manifest.py
```

Use `bunkenn/manifest.production.xml` in Word.
