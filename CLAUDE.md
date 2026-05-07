# email-triage

Local agentic email triage for Outlook. Sister project to `AgenticCodingSystem`.

## Architecture

| Component | Path | Purpose |
|---|---|---|
| Skill | `skill/SKILL.md` | Claude Code skill definition. Symlinked to `~/.claude/skills/email-triage` by `bootstrap.ps1`. |
| Dashboard | `dashboard/app.py` | Streamlit UI on `localhost:8501`. Same DB. |
| Core | `core/` | DB schema (`db.py`), categories (`categories.yaml`), classifier (`classifier.py`), seed (`seed_demo.py`), i18n (`i18n.py`). |
| Data | `data/` | SQLite DB + attachments. Not committed. |

The **DB is the source of truth** — both the skill and the dashboard read/write it. Anything you classify, draft, or mark done from chat shows up in the dashboard on next refresh, and vice versa.

## Demo data flag

Every row has `is_demo` (1 or 0). `wipe-demo` removes only `is_demo=1` rows so seeded mock data can be cleaned without touching real emails.

## Common tasks

| Task | Command |
|---|---|
| Init DB | `uv run python -m core.db init` |
| Seed 18 demo emails | `uv run python -m core.seed_demo` |
| Wipe demo only | `uv run python -m core.db wipe-demo` |
| Wipe everything | `uv run python -m core.db wipe-all` |
| Run dashboard | `uv run streamlit run dashboard/app.py` |

## Categories

Defined in `core/categories.yaml`. Bilingual (zh + en). Editable any time — no restart for skill, just refresh dashboard.

## Bilingual

Dashboard supports zh/en switch in the sidebar. When this skill writes a `summary` it should also write `summary_en`. When it writes a `todos.description` it should also write `description_en`. This keeps the language switch instant and offline.

## When to use the skill

If the user says any of:
- "process emails / triage / 分类 / 整理邮件"
- "draft replies for X / 起草回复"
- "summarize my inbox / 总结收件箱"
- "what's pending / 还有什么没做"
- "wipe demo data / 清除 demo 数据"

→ invoke the `email-triage` skill.

## Outlook integration

Wired up. Code lives in `core/outlook.py` (Graph REST + MSAL device-code flow) and `core/ingest.py` (the `outlook` subcommand).

- Auth: device-code flow via MSAL, no callback URL needed
- Token cache: `data/.token_cache.json` (gitignored)
- Credentials: `.env` (gitignored) with `OUTLOOK_CLIENT_ID` + `OUTLOOK_TENANT_ID`
- Setup guide: [docs/outlook-setup.md](docs/outlook-setup.md)
- Drafts go to Outlook Drafts folder (threaded reply via `createReply`); **never auto-sent**
- Real emails arrive with `is_demo=0`; demo wipe leaves them alone

### Commands the skill should know

| Command | Purpose |
|---|---|
| `python -m core.outlook login` | One-time device-code flow |
| `python -m core.outlook whoami` | Verify authenticated account |
| `python -m core.outlook list --top N` | Quick list of inbox |
| `python -m core.ingest outlook --top N [--unread-only] [--since ISO]` | Pull into DB |
| `python -m core.outlook push-drafts [--dry-run]` | Push DB drafts → Outlook Drafts folder |
| `python -m core.outlook logout` | Clear cached token |
