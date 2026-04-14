# Azure Environment Variables

Set these values in the Azure Static Web App environment variables when you want the deployed
API to read real `bunkenn` data from Supabase.

Required:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `BUNKEN_DEFAULT_USER_ID`

Optional:

- `BUNKEN_DEFAULT_USERNAME`
- `BUNKEN_DEFAULT_EMAIL`

Example:

```text
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=<anon-or-service-role-key>
BUNKEN_DEFAULT_USER_ID=<papers.user_id value>
BUNKEN_DEFAULT_USERNAME=cloud-user
BUNKEN_DEFAULT_EMAIL=
```

Behavior:

- When `SUPABASE_URL` and `SUPABASE_KEY` are set, the deployed API reads papers from Supabase.
- When they are missing, the API falls back to local SQLite if available.
- When neither Supabase nor SQLite is available, the API falls back to `sample_papers.json`.
