# Deployment

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
