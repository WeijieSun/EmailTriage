"""Email ingestion. Multi-account aware.

Two modes:
- `simulate`: drops random fresh demo emails (status='new', is_demo=1).
  Demo emails are spread across 3 mock accounts so multi-account UI can be
  shown without real Outlook.
- `outlook`: pulls real emails from Microsoft Graph via core.outlook
  (status='new', is_demo=0). Supports --account <email> or --all-accounts.

Both modes deduplicate on `message_id` so re-running is safe.
"""
from __future__ import annotations

import argparse
import html
import json
import random
import re
from datetime import datetime
from pathlib import Path
from .db import get_conn, init_db
from .classifier import classify_keyword


MOCK_ACCOUNTS = ["sunweijie0915@outlook.com"]


NEW_ARRIVAL_POOL = [
    # ---- Orders ----
    {
        "from_addr": "amy.lin@newcorp.com",
        "from_name": "Amy Lin",
        "subject": "新订单：80 套配件C",
        "body": "您好，我们想下单 80 套配件C，希望 6/5 前到货。订单号 NEW-2026-0501。",
        "summary": "Amy Lin 下单 80 套配件C，6/5 交期",
        "summary_en": "Amy Lin ordered 80 sets of accessory C, due 6/5",
        "key_fields": {"customer_name": "Amy Lin", "order_id": "NEW-2026-0501", "product": "配件C", "quantity": "80套", "delivery_date": "6/5"},
        "todo_zh": "确认 Amy Lin 订单 NEW-2026-0501",
        "todo_en": "Confirm Amy Lin's order NEW-2026-0501",
    },
    {
        "from_addr": "tom.wright@buyer.io",
        "from_name": "Tom Wright",
        "subject": "PO #9821 - 500 widgets",
        "body": "Please confirm PO #9821 for 500 widgets. Need delivery in 14 days.",
        "summary": "Tom Wright 下单 500 widgets，14 天内交付",
        "summary_en": "Tom Wright ordered 500 widgets, 14-day delivery",
        "key_fields": {"customer_name": "Tom Wright", "order_id": "9821", "product": "widgets", "quantity": "500", "delivery_date": "14 days"},
        "todo_zh": "回复 Tom Wright 确认 PO #9821",
        "todo_en": "Reply to Tom Wright confirming PO #9821",
    },
    # ---- Invoice ----
    {
        "from_addr": "ar@vendor-new.com",
        "from_name": "Vendor New AR",
        "subject": "Invoice INV-NEW-042 - $2,800",
        "body": "Invoice INV-NEW-042 for $2,800 attached. Net 30, due 6/10. Tax ID 88-7654321.",
        "summary": "Vendor New 发票 INV-NEW-042，$2,800，6/10 到期",
        "summary_en": "Vendor New invoice INV-NEW-042 for $2,800, due 6/10",
        "key_fields": {"invoice_no": "INV-NEW-042", "amount": "$2,800", "tax_id": "88-7654321", "due_date": "6/10"},
        "todo_zh": "处理 Vendor New 发票 INV-NEW-042",
        "todo_en": "Process Vendor New invoice INV-NEW-042",
        "attachment": "INV-NEW-042.pdf",
    },
    # ---- Material ----
    {
        "from_addr": "sourcing@megacorp.com",
        "from_name": "MegaCorp Sourcing",
        "subject": "RFQ - 200pcs aluminum brackets",
        "body": "Looking for a quote on 200pcs aluminum brackets, spec attached. Need answer by Wednesday.",
        "summary": "MegaCorp 询价 200 个铝支架，周三前需报价",
        "summary_en": "MegaCorp RFQ: 200pcs aluminum brackets, response by Wed",
        "key_fields": {"item": "aluminum brackets", "quantity": "200pcs", "target_price": "TBD", "vendor": "MegaCorp"},
        "todo_zh": "回复 MegaCorp 铝支架报价",
        "todo_en": "Send MegaCorp aluminum bracket quote",
    },
    # ---- Inquiry ----
    {
        "from_addr": "interested@newprospect.com",
        "from_name": "Curious Buyer",
        "subject": "请问有没有产品演示视频？",
        "body": "您好，看了贵司网站，想了解产品B的实际操作，有没有视频教程？谢谢。",
        "summary": "潜在客户咨询产品B演示视频",
        "summary_en": "Prospect asking for Product B demo video",
        "key_fields": {"topic": "产品B 演示", "urgency": "low", "needs_technical_answer": "no"},
        "todo_zh": "发送产品B 演示视频链接",
        "todo_en": "Send Product B demo video link",
    },
    {
        "from_addr": "hot.lead@enterprise.com",
        "from_name": "Hot Lead",
        "subject": "Urgent: pricing for Q3 deployment",
        "body": "Hi, our team is evaluating vendors for Q3. Can we get pricing for 100 units? Decision by end of week.",
        "summary": "热线索 Q3 100 套询价，本周需决定",
        "summary_en": "Hot lead asking Q3 pricing for 100 units, decision this week",
        "key_fields": {"topic": "Q3 pricing 100 units", "urgency": "high", "needs_technical_answer": "yes"},
        "todo_zh": "紧急回复 Hot Lead Q3 报价",
        "todo_en": "Urgent: reply to Hot Lead with Q3 pricing",
    },
    # ---- Other ----
    {
        "from_addr": "no-reply@calendar.com",
        "from_name": "Calendar Bot",
        "subject": "Reminder: team standup tomorrow 9am",
        "body": "This is an automated reminder. Team standup tomorrow at 9:00 AM PT.",
        "summary": "团队站会提醒，明早 9 点",
        "summary_en": "Team standup reminder, tomorrow 9am",
        "key_fields": {},
        "todo_zh": None,
        "todo_en": None,
    },
]


def _account_for_category(cat_id: str) -> str:
    return MOCK_ACCOUNTS[0]


def simulate(n: int = 3, account: str | None = None):
    """Insert N random fresh 'new' emails. Idempotent across runs.

    Each email is assigned to a mock account based on its category (or to the
    explicitly requested account if provided).
    """
    init_db()
    n = max(1, min(n, len(NEW_ARRIVAL_POOL)))
    picks = random.sample(NEW_ARRIVAL_POOL, n)
    ts = int(datetime.now().timestamp())
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    inserted = 0
    for i, e in enumerate(picks):
        cat_id, conf = classify_keyword(e["subject"], e["body"])
        message_id = f"sim-{ts}-{i}"
        acc = account or _account_for_category(cat_id)
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO emails
            (message_id, account_id, from_addr, from_name, subject, body, category,
             category_confidence, summary, summary_en, key_fields, status, received_at, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, 1)
            """,
            (
                message_id,
                acc,
                e["from_addr"],
                e["from_name"],
                e["subject"],
                e["body"],
                cat_id,
                conf,
                e["summary"],
                e["summary_en"],
                json.dumps(e["key_fields"], ensure_ascii=False),
                now,
            ),
        )
        if cur.rowcount == 0:
            continue
        email_id = cur.lastrowid
        inserted += 1

        if e.get("attachment"):
            conn.execute(
                """
                INSERT INTO attachments (email_id, filename, local_path, size_bytes, is_demo)
                VALUES (?, ?, ?, ?, 1)
                """,
                (email_id, e["attachment"], f"data/attachments/demo/{e['attachment']}", 102400),
            )

        if e.get("todo_zh"):
            conn.execute(
                """
                INSERT INTO todos (email_id, description, description_en, status, created_at, is_demo)
                VALUES (?, ?, ?, 'pending', ?, 1)
                """,
                (email_id, e["todo_zh"], e["todo_en"], now),
            )

    conn.commit()
    conn.close()
    print(f"Simulated {inserted} new emails arriving (status='new').")


def _strip_html(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _ingest_outlook_one(account: str, top: int, since: str | None, unread_only: bool, fetch_attachments: bool) -> int:
    """Pull from a single account."""
    from . import outlook as ol

    filters = []
    if since:
        filters.append(f"receivedDateTime ge {since}")
    if unread_only:
        filters.append("isRead eq false")
    filter_ = " and ".join(filters) if filters else None

    msgs = ol.list_inbox(top=top, filter_=filter_, account=account)

    conn = get_conn()
    inserted = 0
    skipped = 0
    attach_dir_root = Path(__file__).resolve().parent.parent / "data" / "attachments"

    for m in msgs:
        message_id = m["id"]
        if conn.execute("SELECT 1 FROM emails WHERE message_id = ?", (message_id,)).fetchone():
            skipped += 1
            continue

        from_ea = (m.get("from") or {}).get("emailAddress") or {}
        from_addr = from_ea.get("address", "")
        from_name = from_ea.get("name", "")
        subject = m.get("subject", "") or ""
        body_obj = m.get("body") or {}
        body_text = (
            _strip_html(body_obj.get("content", ""))
            if body_obj.get("contentType") == "html"
            else body_obj.get("content", "") or m.get("bodyPreview", "")
        )
        received = m.get("receivedDateTime")

        cat_id, conf = classify_keyword(subject, body_text)

        cur = conn.execute(
            """
            INSERT INTO emails
            (message_id, account_id, from_addr, from_name, subject, body, category,
             category_confidence, status, received_at, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, 0)
            """,
            (message_id, account, from_addr, from_name, subject, body_text, cat_id, conf, received),
        )
        email_id = cur.lastrowid
        inserted += 1

        if fetch_attachments and m.get("hasAttachments"):
            try:
                atts = ol.list_attachments(message_id, account=account)
            except Exception as e:
                print(f"  warn: could not list attachments for {message_id[:20]}: {e}")
                atts = []
            for att in atts:
                if att.get("@odata.type") != "#microsoft.graph.fileAttachment":
                    continue
                save_dir = attach_dir_root / message_id[:30]
                save_path = save_dir / att["name"]
                try:
                    ol.download_attachment(message_id, att["id"], save_path, account=account)
                except Exception as e:
                    print(f"  warn: could not download {att['name']}: {e}")
                    continue
                rel_path = save_path.relative_to(attach_dir_root.parent.parent).as_posix()
                conn.execute(
                    """
                    INSERT INTO attachments (email_id, filename, local_path, size_bytes, is_demo)
                    VALUES (?, ?, ?, ?, 0)
                    """,
                    (email_id, att["name"], rel_path, att.get("size", 0)),
                )

    conn.commit()
    conn.close()
    print(f"  {account}: ingested {inserted} new, skipped {skipped} duplicate(s).")
    return inserted


def ingest_outlook(
    top: int = 50,
    since: str | None = None,
    unread_only: bool = False,
    fetch_attachments: bool = True,
    account: str | None = None,
    all_accounts: bool = False,
) -> int:
    """Pull recent emails into the DB. Multi-account aware.

    - all_accounts=True: loop over every signed-in MSAL account
    - account=email: only that account
    - neither: only valid if exactly one account is signed in
    """
    from . import outlook as ol
    init_db()

    if all_accounts:
        accs = ol.list_accounts()
        if not accs:
            raise RuntimeError("No signed-in accounts. Run: python -m core.outlook login")
        total = 0
        for a in accs:
            print(f"\n--- account: {a['username']} ---")
            total += _ingest_outlook_one(a["username"], top, since, unread_only, fetch_attachments)
        return total

    if account is None:
        accs = ol.list_accounts()
        if not accs:
            raise RuntimeError("No signed-in accounts. Run: python -m core.outlook login")
        if len(accs) > 1:
            names = ", ".join(a["username"] for a in accs)
            raise RuntimeError(
                f"Multiple accounts signed in ({names}). Use --account <email> or --all-accounts."
            )
        account = accs[0]["username"]

    return _ingest_outlook_one(account, top, since, unread_only, fetch_attachments)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)

    p_sim = sub.add_parser("simulate", help="Drop N fresh demo emails (status='new', is_demo=1)")
    p_sim.add_argument("-n", type=int, default=3, help="number of emails (default 3)")
    p_sim.add_argument("--account", help="Pin all simulated emails to this account (default: by category)")

    p_ol = sub.add_parser("outlook", help="Pull real emails from Outlook (is_demo=0)")
    p_ol.add_argument("--top", type=int, default=25, help="max messages to fetch")
    p_ol.add_argument("--since", help="ISO timestamp, e.g. 2026-05-01T00:00:00Z")
    p_ol.add_argument("--unread-only", action="store_true")
    p_ol.add_argument("--no-attachments", action="store_true", help="Skip attachment download")
    grp = p_ol.add_mutually_exclusive_group()
    grp.add_argument("--account", help="Pull from this account (required if 2+ signed in)")
    grp.add_argument("--all-accounts", action="store_true", help="Pull from every signed-in account")

    args = parser.parse_args()
    if args.action == "simulate":
        simulate(args.n, account=args.account)
    elif args.action == "outlook":
        try:
            ingest_outlook(
                top=args.top,
                since=args.since,
                unread_only=args.unread_only,
                fetch_attachments=not args.no_attachments,
                account=args.account,
                all_accounts=args.all_accounts,
            )
        except RuntimeError as e:
            import sys
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
