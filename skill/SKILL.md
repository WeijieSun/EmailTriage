---
name: email-triage
description: Process Outlook emails (multi-account) — fetch, classify by category (orders / invoices / materials / inquiries / other), extract structured key fields, generate drafts in batch, push drafts to Outlook drafts folder, and write everything to a shared SQLite DB so the localhost:8501 dashboard stays in sync. Use when the user asks to fetch / pull / triage / process / classify / draft / push / mark-done emails, ask about email status, or manage Outlook accounts.
---

# email-triage skill

This skill drives the agentic side of the **email-triage** project. The dashboard at `localhost:8501` is the user's primary surface; this skill is the "do work" side. Both read and write the same SQLite DB.

## How to interpret the user (natural-language → command playbook)

**Match the user's request to one of these intents and run the matching command(s) via Bash. Don't just chat — actually run things.**

| User says (any language, any phrasing) | Run |
|---|---|
| "拉新邮件" / "fetch new emails" / "check inbox" / "有新邮件吗" | `python -m core.ingest outlook --top 50 --unread-only --all-accounts` |
| "拉 X 邮箱的新邮件" / "fetch from X account" | `python -m core.ingest outlook --top 50 --unread-only --account X` |
| "处理未处理的" / "process new" / "归类邮件" / "处理一下" | `python -m core.process run` |
| "处理订单类的" / "draft replies for orders" | `python -m core.process run --category order` |
| "看下现状" / "summary" / "what's pending" / "还有什么没做" | `python -m core.process status` |
| "推草稿" / "push drafts to outlook" / "把草稿放到草稿箱" | first `python -m core.outlook push-drafts --dry-run --all-accounts` to preview, confirm, then without `--dry-run` |
| "一键日常" / "everything" / "fetch and process and push" | run all three: ingest outlook → process run → push-drafts (per account, --all-accounts on each) |
| "看我有几个邮箱" / "list accounts" | `python -m core.outlook accounts` |
| "登录另一个邮箱" / "add an outlook account" / "登录" | `python -m core.outlook login` (note: this is interactive — print the device-code message you see, the user follows it manually) |
| "把 X 邮箱登出" / "remove X account" | `python -m core.outlook logout --account X` |
| "全部登出" / "log out everything" | confirm first, then `python -m core.outlook logout` |
| "模拟几封新邮件" / "simulate" (for demos) | `python -m core.ingest simulate -n 3` |
| "清 demo 数据" / "wipe demo" | confirm first, then `python -m core.db wipe-demo` |
| "加一个分类叫 X" / "add a category" | edit `core/categories.yaml` (interactive — ask user for keywords + key_fields + zh/en draft templates) |
| "标记 X 完成" / "mark email N done" | UPDATE the DB row's status='completed' |

### Disambiguation rules

- **If the user is vague about which account** (multiple accounts signed in): ask "from which account? Available: <list from `python -m core.outlook accounts`>" — or default to `--all-accounts` if the request says "all" / "全部".
- **If push-drafts is requested**, ALWAYS run `--dry-run` first and show the user the preview before pushing for real. Confirm before the second run.
- **If 0 accounts signed in** and user asks anything Outlook-related: tell them to run `python -m core.outlook login` first.
- **For destructive actions** (wipe-demo, wipe-all, logout without --account): confirm before running.

## Project layout (relative to project root)

```
core/db.py                  schema + helpers (init / wipe-demo / wipe-all)
core/categories.yaml        category config
core/classifier.py          keyword classifier (fallback when running without Claude)
core/process.py             incremental processor — picks up status='new' rows
core/ingest.py              ingest: simulate (mock) | outlook (real, multi-account)
core/outlook.py             MSAL + Graph wrapper, multi-account aware
core/seed_demo.py           seeds 18 demo emails across 3 mock accounts
core/i18n.py                zh/en strings for dashboard
dashboard/app.py            Streamlit dashboard (localhost:8501)
data/emails.db              SQLite DB
data/.token_cache.json      MSAL token cache (multi-account, gitignored)
data/attachments/           where attachments are saved
```

## Important rules

- **Always write to the DB.** Don't just respond in chat — the dashboard is the source of truth for status. After any batch action, tell the user to refresh `localhost:8501`.
- **Incremental by default.** Re-running `process run` only touches `status='new'` rows. Already-processed (`drafted` / `completed`) emails are skipped.
- **Never auto-send.** Drafts go to the Outlook **Drafts** folder via `push-drafts` (threaded replies). The user must hit Send themselves.
- **Multi-account** is real and per-row: every email row has an `account_id`. When fetching/pushing, target a specific account or use `--all-accounts`.
- **Demo vs. real:** rows have `is_demo` (1 = demo, 0 = real). Demo data is across 3 mock accounts (`work@d3security.com`, `sales@d3security.com`, `personal@outlook.com`). `wipe-demo` only removes `is_demo=1`.
- **Bilingual.** When you write `summary`, also write `summary_en`. When you write a `todos.description`, also write `description_en`.
- **Categories live in YAML.** Read `core/categories.yaml` for the live list; never hardcode.

## Status lifecycle (the "processed marker")

| status | meaning | who sets |
|---|---|---|
| `new` | just landed, untouched by AI | inserted by ingest / seed |
| `drafted` | AI classified + summarized + drafted reply | this skill (or `core/process.py`) |
| `completed` | user signed off | dashboard "mark done" or skill |

`processed_at` records when AI last touched a row.

## Multi-account specifics

- The same Azure App is used for all accounts (one `OUTLOOK_CLIENT_ID` in `.env`). Users add accounts by re-running `python -m core.outlook login` and signing in with each one.
- The MSAL token cache (`data/.token_cache.json`) holds tokens for all signed-in accounts simultaneously.
- When CLI commands need an account but multiple are signed in:
  - `--account <email>` selects one
  - `--all-accounts` fans out
  - omitting both = error with a helpful list of available accounts
- The `account_id` column on emails is the user's email address (lowercase). Filter / group by it freely.

## DB cheat sheet

```python
from core.db import get_conn
import json

# Update a single email after classification (always set both languages):
conn = get_conn()
conn.execute("""
    UPDATE emails
    SET category = ?, category_confidence = ?, summary = ?, summary_en = ?,
        key_fields = ?, processed_at = datetime('now')
    WHERE id = ?
""", (cat_id, conf, summary_zh, summary_en,
      json.dumps(kf, ensure_ascii=False), email_id))
conn.commit()

# Add a to-do (always with both languages)
conn.execute("""
    INSERT INTO todos (email_id, description, description_en, status, created_at, is_demo)
    VALUES (?, ?, ?, 'pending', datetime('now'), ?)
""", (email_id, desc_zh, desc_en, is_demo))
conn.commit()
```

## How to think about classification

Use keywords in `categories.yaml` as **hints**, not rules. A subject like "Re: 我们想了解贵司的 OEM 服务" matches both `material` (采购) and `inquiry` (了解) — read the body to decide.

Confidence:
- 0.9+ : strong signals, multiple matches, clear intent
- 0.7–0.9 : clear but mixed
- 0.5–0.7 : best guess
- < 0.5 : `other`

## Demo flow recipe (the user is showing this off)

1. `python -m core.seed_demo` — 18 demo emails across 3 mock accounts.
2. `streamlit run dashboard/app.py` — banner: "🆕 18 待处理"; sidebar shows account filter.
3. Click the 🚀 一键日常 button → source = "Demo 模拟" → fetch + process happen, banner flips.
4. Or, in chat: "处理一下未处理的" → run `python -m core.process run`.
5. `python -m core.ingest simulate -n 3` to demo incremental — only the 3 new ones get processed next run.
6. Toggle account filter in sidebar → emails segregate by account.
7. Toggle 中文/English → UI flips.
8. When done: `python -m core.db wipe-demo`.

## Real Outlook flow recipe

1. User completes Azure App + .env setup (see `docs/outlook-setup.md`)
2. `python -m core.outlook login` per account (each adds to the cache)
3. `python -m core.outlook accounts` to verify
4. `python -m core.ingest outlook --all-accounts --top 50 --unread-only` to pull
5. `python -m core.process run` to classify + draft
6. `python -m core.outlook push-drafts --all-accounts --dry-run` to preview
7. `python -m core.outlook push-drafts --all-accounts` to push for real
8. User reviews drafts in Outlook Drafts folder, hits Send manually.
