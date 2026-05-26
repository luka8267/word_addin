# Chrome Extension Release Checklist

Use this checklist before marking the bunken Chrome extension save flow as complete.

## Static and API verification

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-ExtensionRelease.ps1
```

Required result:

- Local extension checks pass.
- Python API tests pass.
- Python compile checks pass.
- GitHub raw manifest version matches the local manifest.
- Release ZIP manifest version matches the local manifest.
- Production `/api/addin/extension/save` returns CORS headers and `401 Unauthorized` without credentials.

## Authenticated production smoke

Prefer a test bunken account.

Run either:

```powershell
$env:BUNKEN_EXTENSION_ACCESS_TOKEN="<Supabase access token>"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-ExtensionRelease.ps1 -RunAuthenticatedSmoke
```

or:

```powershell
$env:BUNKEN_EXTENSION_EMAIL="<email>"
$env:BUNKEN_EXTENSION_PASSWORD="<password>"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-ExtensionRelease.ps1 -RunAuthenticatedSmoke
```

Required result:

- The smoke paper is saved through `/api/addin/extension/save`.
- Posting the same DOI again returns `duplicate=true`.
- `/api/addin/papers?q=<doi>` finds the saved paper.
- The PDF result is reported. `pdf.saved=true` confirms Storage + attachment creation. If `pdf.saved=false`, the response must include `pdfCandidates` and a reason for manual upload.

## Browser extension smoke

1. Open bunken and confirm the Chrome extension sidebar says the expected version, for example `ダウンロード版: v0.2.6`.
2. Download the ZIP and extract it.
3. Open `chrome://extensions` or `brave://extensions`.
4. Remove the old `bunken Web Importer` extension if installed.
5. Load the extracted `bunken-web-importer` folder with `Load unpacked`.
6. Open a real paper landing page with DOI metadata.
7. Open the extension popup.
8. Confirm the popup shows title, DOI, and PDF candidate count.
9. Log in with the same bunken account.
10. Click `bunken に保存`.

Required result:

- First save reports `bunken に保存しました。`
- Repeating the save reports `すでに bunken に登録されています。`
- If a PDF can be fetched by the API, the popup reports PDF saved.
- If the publisher blocks API PDF fetching, the popup shows a PDF candidate and tells the user to upload manually.
- The paper appears in the bunken list after refresh.

## Completion decision

The goal can be marked complete only after:

- Static and API verification passes.
- Authenticated production smoke passes, or the browser extension smoke proves the same save + duplicate + list visibility flow.
- The downloaded extension ZIP version matches the version shown in bunken.
- No DB schema changes are pending.
