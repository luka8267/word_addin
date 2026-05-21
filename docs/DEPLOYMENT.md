# Deployment

## Recommended Free Host

Use Vercel Hobby when Azure is unavailable. Vercel can serve the static task pane
and Python API from the same origin.

Vercel files in this repo:

- `vercel.json`
- `api/addin/*`
- `requirements.txt`
- `package.json`

## Current Production Host

Run `bunken Word` without localhost by hosting the task pane and API on Vercel.

Production URL currently used by the manifest:

```text
https://word-addin-sooty.vercel.app
```

## GitHub Actions

The Azure Static Web Apps workflow is kept only as a manual legacy fallback:

```text
.github/workflows/azure-static-web-apps-jolly-smoke-0e8ae9a10.yml
```

It is intentionally `workflow_dispatch` only. Do not use it for normal
deployment unless Azure Static Web Apps is restored and the deployment token is
rotated. Normal production deploys happen on Vercel from the `main` branch.

The legacy Azure workflow deploys:

- Static app: `bunkenn/azure-static-web-apps/static`
- API: `bunkenn/azure-static-web-apps/api`

Required GitHub secret:

```text
AZURE_STATIC_WEB_APPS_API_TOKEN_JOLLY_SMOKE_0E8AE9A10
```

If this secret is missing, expired, or belongs to a deleted Static Web App,
manual Azure runs fail with `No matching Static Web App was found or the api key
was invalid.` This does not affect the Vercel production add-in.

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

This manifest points Word to the Vercel URL, so Word no longer needs the local
Functions host or SWA CLI.

## Vercel Deployment

1. Import `luka8267/word_addin` into Vercel.
2. Use the repository root as the Vercel project root.
3. Keep the framework preset as `Other`.
4. Build command: `npm run build`.
5. Output directory: `public`.
6. Set environment variables:

```text
SUPABASE_URL=https://udhgdndfcmdgpnxpksvo.supabase.co
SUPABASE_PUBLISHABLE_KEY=<Supabase anon or publishable key>
```

Optional debug variable:

```text
BUNKEN_ENABLE_DEBUG_ENDPOINTS=true
```

7. Deploy the `main` branch.
8. Check:

```powershell
curl.exe -L https://<your-vercel-app>.vercel.app/taskpane.html
curl.exe -L "https://<your-vercel-app>.vercel.app/api/addin/papers?_debug=version"
```

9. Generate a production manifest for the Vercel URL:

```powershell
$env:BUNKEN_PUBLIC_BASE_URL="https://<your-vercel-app>.vercel.app"
python bunkenn\generate_manifest.py
```

Use `bunkenn/manifest.production.xml` in Word.
