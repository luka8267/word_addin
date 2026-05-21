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
