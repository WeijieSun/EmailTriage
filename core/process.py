"""Incremental email processor.

Picks up emails with status='new', generates a draft from the category template,
flips status to 'drafted', and stamps processed_at. Already-processed emails
('drafted' / 'completed') are skipped — re-running this picks up only NEW arrivals.

The Claude skill performs the same incremental query but uses Claude for richer
classification + summarization. This CLI is the no-LLM fallback so the
demo loop works even without Claude in the chat.
"""
from __future__ import annotations

import argparse
import json
from .db import get_conn
from .classifier import get_category, render_draft


def process_new(lang: str = "zh", category: str | None = None) -> int:
    """Process emails with status='new'. Returns count of emails processed."""
    conn = get_conn()
    if category:
        rows = conn.execute(
            "SELECT * FROM emails WHERE status = 'new' AND category = ? ORDER BY id",
            (category,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM emails WHERE status = 'new' ORDER BY id").fetchall()

    if not rows:
        conn.close()
        print("No new emails to process. (status='new' set is empty)")
        return 0

    processed = 0
    by_cat: dict[str, int] = {}
    for row in rows:
        cat = get_category(row["category"])
        kf = json.loads(row["key_fields"]) if row["key_fields"] else {}
        template_key = "draft_template_zh" if lang == "zh" else "draft_template_en"
        template = cat.get(template_key) or cat.get("draft_template_zh") or ""

        draft = render_draft(template, kf) if template else ""
        conn.execute(
            """
            UPDATE emails
            SET draft_text = ?, status = 'drafted', processed_at = datetime('now')
            WHERE id = ?
            """,
            (draft, int(row["id"])),
        )
        processed += 1
        by_cat[cat["id"]] = by_cat.get(cat["id"], 0) + 1

    conn.commit()
    conn.close()

    print(f"Processed {processed} email(s):")
    for cid, n in sorted(by_cat.items()):
        print(f"  {cid:10s}  {n}")
    return processed


def status_report() -> None:
    conn = get_conn()
    by_status = conn.execute(
        "SELECT status, COUNT(*) AS n FROM emails GROUP BY status ORDER BY status"
    ).fetchall()
    by_cat = conn.execute(
        "SELECT category, COUNT(*) AS n FROM emails GROUP BY category ORDER BY category"
    ).fetchall()
    last_proc = conn.execute(
        "SELECT MAX(processed_at) FROM emails WHERE processed_at IS NOT NULL"
    ).fetchone()[0]
    pending_todos = conn.execute(
        "SELECT COUNT(*) FROM todos WHERE status='pending'"
    ).fetchone()[0]
    conn.close()

    print("Status:")
    for r in by_status:
        print(f"  {r['status']:12s} {r['n']}")
    print("\nBy category:")
    for r in by_cat:
        print(f"  {r['category']:12s} {r['n']}")
    print(f"\nPending todos: {pending_todos}")
    print(f"Last processed: {last_proc or '(never)'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Incremental email processor.")
    sub = parser.add_subparsers(dest="action", required=True)

    p_run = sub.add_parser("run", help="Process all status='new' emails (incremental)")
    p_run.add_argument("--lang", choices=["zh", "en"], default="zh", help="Draft template language")
    p_run.add_argument("--category", help="Only process this category id")

    sub.add_parser("status", help="Print a status report")

    args = parser.parse_args()
    if args.action == "run":
        process_new(args.lang, args.category)
    elif args.action == "status":
        status_report()
