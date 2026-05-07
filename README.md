# email-triage

Local AI agent that triages Outlook emails: classifies by category, summarizes, extracts to-dos, drafts batch replies, and shows it all on a localhost dashboard. Pairs with [Claude Code](https://docs.anthropic.com/claude/docs/claude-code) — the agent does the work, the dashboard tracks the state.

## Features

- 📂 Configurable categories (default: orders / invoices / materials / inquiries / other)
- 📝 Batch-draft replies per category from a template + extracted fields
- ✅ To-do tracking with one-click status toggle
- 🌐 Chinese / English UI switch
- 📎 Attachment paths recorded per email
- 🧹 Demo-data flag — seed mock emails, wipe them with one command, real data untouched
- 🪟 Single-folder Windows install via `bootstrap.ps1`

## Quick start (Windows)

1. Copy this folder to the target machine.
2. Open PowerShell in the folder.
3. Run:
   ```powershell
   .\bootstrap.ps1
   ```
   The script:
   - Installs Python 3.12 (via winget) if missing
   - Installs uv (fast Python package manager)
   - Installs project dependencies
   - Symlinks the skill into `~/.claude/skills/email-triage`
   - Initializes the SQLite DB
   - Optionally seeds 18 demo emails
4. Start the dashboard:
   ```powershell
   uv run streamlit run dashboard/app.py
   ```
5. Open Claude Code in this folder. Try:
   ```
   process all my new emails
   ```
   Claude will pick up the `email-triage` skill, classify the seeded demo emails, write summaries / key fields / to-dos, and update the DB. Refresh the dashboard to see results.

## Switching from demo to real Outlook

Demo data is flagged `is_demo=1`. To clean it:

```powershell
uv run python -m core.db wipe-demo
```

Real data has `is_demo=0` and is **never** touched by `wipe-demo`.

### One-time Outlook setup

See [docs/outlook-setup.md](docs/outlook-setup.md) for step-by-step Azure App registration. TL;DR:

1. Register an app in Azure Portal, allow **public client flows**, grant `Mail.ReadWrite` permission.
2. Copy `.env.example` → `.env`, paste in `OUTLOOK_CLIENT_ID` (and optionally `OUTLOOK_TENANT_ID`).
3. `uv run python -m core.outlook login` — device-code flow in browser, one-time per machine.

### Daily Outlook commands

```powershell
# Pull recent emails into DB (status='new', is_demo=0)
uv run python -m core.ingest outlook --top 25 --unread-only

# Process the new ones (incremental — skips already-processed)
uv run python -m core.process run

# Push DB drafts to the Outlook Drafts folder (as threaded replies, never sent)
uv run python -m core.outlook push-drafts
```

## Customizing categories

Edit `core/categories.yaml`. Each category needs:

- `id`, `name` (zh), `name_en`
- `keywords` — used by the demo classifier
- `key_fields` — list of structured fields the AI should extract
- `draft_template_zh`, `draft_template_en` — Mustache-ish templates with `{{key_field}}` placeholders

Reload the dashboard to see new tabs.

## File layout

```
.
├── bootstrap.ps1            ← Windows installer
├── pyproject.toml           ← Python deps (uv)
├── requirements.txt         ← Python deps (pip fallback)
├── README.md
├── CLAUDE.md                ← repo context for Claude
├── skill/
│   └── SKILL.md             ← Claude skill definition
├── core/
│   ├── db.py                ← SQLite schema + helpers
│   ├── categories.yaml      ← editable categories
│   ├── classifier.py        ← keyword classifier (demo fallback)
│   ├── seed_demo.py         ← 18 mock emails
│   └── i18n.py              ← zh/en strings
├── dashboard/
│   └── app.py               ← Streamlit UI
└── data/                    ← (created at runtime, gitignored)
    ├── emails.db
    └── attachments/
```

## How it works

```
   ┌─────────────────────┐
   │  Claude Code Skill  │  ← chat-driven agent
   │  (email-triage)     │
   └──────────┬──────────┘
              │ read/write
              ▼
   ┌─────────────────────┐
   │   SQLite (single    │  ← single source of truth
   │   file: emails.db)  │
   └──────────┬──────────┘
              │ read/write
              ▼
   ┌─────────────────────┐
   │  Streamlit          │  ← visual surface
   │  localhost:8501     │
   └─────────────────────┘
```

The skill never sends emails. Drafts are written to the DB; the user reviews and decides what to do.

## License

Internal project.
