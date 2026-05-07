# Outlook setup

This is a one-time setup per Microsoft 365 / Outlook tenant. After this is done,
every machine using the same Azure App reuses the same `OUTLOOK_CLIENT_ID` —
each user just signs in once via the device-code flow.

## 1. Register an Azure App

1. Go to **Azure Portal** → [App registrations](https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade) → **+ New registration**
2. Fill in:
   - **Name**: `email-triage` (anything, just for your reference)
   - **Supported account types**: pick one
     - "Personal Microsoft accounts only" — for outlook.com / hotmail.com personal mailboxes
     - "Accounts in any organizational directory and personal Microsoft accounts" (multitenant) — works everywhere
     - Single-tenant — locks the app to your company tenant
   - **Redirect URI**: leave blank (we use device code flow, no callback needed)
3. Click **Register**.
4. On the app's **Overview** page, copy:
   - **Application (client) ID** → this goes into `.env` as `OUTLOOK_CLIENT_ID`
   - **Directory (tenant) ID** → goes into `OUTLOOK_TENANT_ID` (or use `common` / `organizations` / `consumers`)

## 2. Allow public client flows

Device-code is a "public client" flow. We need to enable it:

1. In the app, go to **Authentication** in the left sidebar.
2. Scroll to **Advanced settings** → **Allow public client flows** → set to **Yes**.
3. Click **Save**.

## 3. Add API permissions

1. Go to **API permissions** → **+ Add a permission** → **Microsoft Graph** → **Delegated permissions**.
2. Search for and add:
   - `Mail.ReadWrite` — read inbox + create drafts
   - `Mail.Send` — only needed if you ever wire up "really send" (we don't auto-send)
   - `User.Read` — basic profile, granted by default
3. Click **Add permissions**.
4. (Work/school tenants only) Click **Grant admin consent for <tenant>** if your tenant requires admin consent.

## 4. Configure email-triage

```powershell
cd C:\path\to\email-triage
copy .env.example .env
notepad .env       # paste your client_id and tenant_id
```

`.env` is gitignored — your credentials stay local.

## 5. Sign in

```powershell
uv run python -m core.outlook login
```

A device-code message appears like:

```
To sign in, use a web browser to open the page https://microsoft.com/devicelogin
and enter the code ABCD1234 to authenticate.
```

Open that URL, paste the code, complete 2FA. Token is cached at
`data/.token_cache.json` (gitignored). Subsequent calls are silent until the
refresh token expires (typically 90 days).

Verify:

```powershell
uv run python -m core.outlook whoami
# → prints displayName + email
```

## 6. Daily commands

```powershell
# Pull recent inbox messages into the DB (status='new')
uv run python -m core.ingest outlook --top 25

# Pull only unread, since a date
uv run python -m core.ingest outlook --top 100 --since 2026-05-01T00:00:00Z --unread-only

# Process the new ones (incremental — already-processed are skipped)
uv run python -m core.process run

# Push DB drafts up to Outlook drafts folder (as threaded replies)
uv run python -m core.outlook push-drafts

# Dry run first if you want to preview
uv run python -m core.outlook push-drafts --dry-run
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `OUTLOOK_CLIENT_ID is not set` | `.env` missing or not in project root. `copy .env.example .env`, fill it in. |
| `AADSTS65001: The user or administrator has not consented` | Step 3 missing, or admin consent required. |
| `AADSTS7000218: The request body must contain... client_assertion or client_secret` | Step 2 missing — public client flows not enabled. |
| `403 Forbidden` on `/me/messages` | `Mail.ReadWrite` permission not added or not consented. |
| Need to re-login | `uv run python -m core.outlook logout`, then `login` again. |
| Want to use a different account | `logout`, `login` — pick the new account in the browser. |

## Security notes

- The `client_id` is **public** — it's safe to commit (it's not a secret). The .env approach just keeps it portable per-machine.
- The **token cache** (`data/.token_cache.json`) IS sensitive — gitignored.
- Tokens are scoped only to mail (`Mail.ReadWrite`, `Mail.Send`), never to OneDrive / Teams / etc.
- Refresh tokens can be revoked from `https://account.activedirectory.windowsazure.com/r#/applications` (or your org's portal) at any time.
