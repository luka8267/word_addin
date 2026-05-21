# Deployment

## Production Host

The Word add-in is deployed on Vercel. Vercel serves the static task pane and
the Python API from the same origin.

Production URL currently used by the manifest:

```text
https://word-addin-sooty.vercel.app
```

Vercel files in this repo:

- `vercel.json`
- `api/addin/*`
- `requirements.txt`
- `package.json`
- `bunkenn/word-app/static`
- `bunkenn/word-app/api/shared`

## Word Add-in Manifest

Use:

```text
bunkenn/manifest.production.xml
```

This manifest points Word to the Vercel URL, so Word does not need localhost.

Generate a production manifest for a new Vercel URL:

```powershell
$env:BUNKEN_PUBLIC_BASE_URL="https://<your-vercel-app>.vercel.app"
python bunkenn\generate_manifest.py
```

Use the generated `bunkenn/manifest.production.xml` in Word.

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

Keep debug endpoints disabled in normal production:

```text
BUNKEN_ENABLE_DEBUG_ENDPOINTS=false
```

7. Deploy the `main` branch.
8. Check:

```powershell
curl.exe -L https://<your-vercel-app>.vercel.app/taskpane.html
curl.exe -L "https://<your-vercel-app>.vercel.app/api/addin/papers?_debug=version"
```

Expected API version:

```json
{"version":"citation-context-sync-v1"}
```

## Local Environment

For local Vercel-compatible testing:

```powershell
npm install
npm run build
npx vercel dev
```

Use the URL shown by Vercel, usually:

```text
http://localhost:3000/taskpane.html
```

Generate a local manifest for that URL:

```powershell
$env:BUNKEN_LOCAL_BASE_URL="http://localhost:3000"
python bunkenn\generate_manifest.py --local
```

Prepare the Word shared-folder catalog:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Prepare-LocalWordSideload.ps1 -BaseUrl "http://localhost:3000" -CheckLocalServer -CreateShare
```

If Word keeps showing old UI:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Clear-WordAddinCache.ps1 -CloseWord
```

## Manifest Management

- Production manifest: `bunkenn/manifest.production.xml`
- Default checked-in manifest: `bunkenn/manifest.xml`
- Local generated manifests: `bunkenn/manifest.local*.xml`, ignored by Git
- Windows shared-folder copy:
  `%USERPROFILE%\Documents\bunken-word-addin-catalog\manifest.xml`

When the Vercel URL changes:

```powershell
$env:BUNKEN_PUBLIC_BASE_URL="https://<new-vercel-app>.vercel.app"
python bunkenn\generate_manifest.py
git diff -- bunkenn\manifest.production.xml bunkenn\manifest.xml
```

After replacing a manifest in Word, restart Word and clear cache if necessary.

## Release Checks

Before pushing:

```powershell
python -m py_compile `
  api\_bunken_vercel.py `
  bunkenn\word-app\api\shared\data_access.py `
  bunkenn\word-app\api\shared\bunken_service.py `
  bunkenn\word-app\api\shared\bunken_models.py
python -m unittest discover -s tests -v
node --check bunkenn\word-app\static\taskpane.js
npm run build
```

After deploy:

- taskpane loads
- login works
- search works by title, DOI, year, tag, and collection
- citation insertion works
- reference list update does not duplicate old bibliography blocks
- style switching updates existing citations
- document citation sync updates context counts

## Logs and Troubleshooting

Vercel:

- Project > Deployments > latest deployment > Build Logs
- Project > Deployments > latest deployment > Functions logs
- Check `/api/addin/papers?_debug=version` only when debug endpoints are enabled.

Word Desktop:

- A 404 usually means the manifest URL points to the wrong static location.
- An old UI usually means Word cached the add-in.
- A login/search error usually means Vercel env vars or Supabase auth/RLS failed.

Supabase:

- API logs show REST/RLS failures.
- Auth logs show login/session failures.
- Postgres logs show SQL errors.
