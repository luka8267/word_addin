# bunken Word App

This folder contains the Word add-in UI and shared API code used by the Vercel
deployment.

## Structure

```text
word-app/
  static/          Office task pane files, icons, and command files
  api/shared/      Supabase and citation logic shared by Vercel handlers
```

The Vercel entry points live at the repository root under `api/addin/*`. They
import shared code from `api/shared`.

## Static Build

```powershell
npm run build
```

This copies `bunkenn\word-app\static` to the root `public` directory for Vercel.

## API Checks

```powershell
python -m py_compile `
  api\_bunken_vercel.py `
  bunkenn\word-app\api\shared\data_access.py `
  bunkenn\word-app\api\shared\bunken_service.py `
  bunkenn\word-app\api\shared\bunken_models.py
```
