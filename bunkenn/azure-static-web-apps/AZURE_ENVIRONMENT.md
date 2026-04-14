# Azure Environment Variables

Set these values in the Azure Static Web App environment variables when you want the deployed
API to read real `bunkenn` data from Supabase.

Required:

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `BUNKEN_DEFAULT_USER_ID`

Optional:

- `SUPABASE_KEY`
- `BUNKEN_DEFAULT_USERNAME`
- `BUNKEN_DEFAULT_EMAIL`

Example:

```text
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<publishable-or-anon-key>
SUPABASE_KEY=<service-role-or-secret-key>
BUNKEN_DEFAULT_USER_ID=<papers.user_id value>
BUNKEN_DEFAULT_USERNAME=cloud-user
BUNKEN_DEFAULT_EMAIL=
```

Behavior:

- When `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` are set, user login and user-scoped paper search work.
- When `SUPABASE_KEY` is also set, server-side fallback queries can run without a user token.
- When they are missing, the API falls back to local SQLite if available.
- When neither Supabase nor SQLite is available, the API falls back to `sample_papers.json`.
