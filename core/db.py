"""SQLite schema + helpers. Single source of truth for the dashboard and the skill.

Demo rows are tagged is_demo=1 so they can be wiped without touching real data.
"""
import sqlite3
import argparse
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "emails.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE,
    account_id TEXT,
    from_addr TEXT,
    from_name TEXT,
    subject TEXT,
    body TEXT,
    category TEXT,
    category_confidence REAL,
    summary TEXT,
    summary_en TEXT,
    key_fields TEXT,
    status TEXT DEFAULT 'new',
    draft_text TEXT,
    outlook_draft_id TEXT,
    draft_pushed_at TEXT,
    received_at TEXT,
    processed_at TEXT,
    is_demo INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER,
    filename TEXT,
    local_path TEXT,
    size_bytes INTEGER,
    is_demo INTEGER DEFAULT 0,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER,
    description TEXT,
    description_en TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    completed_at TEXT,
    is_demo INTEGER DEFAULT 0,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_emails_category ON emails(category);
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
CREATE INDEX IF NOT EXISTS idx_emails_demo ON emails(is_demo);
"""


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


_MIGRATIONS = [
    "ALTER TABLE emails ADD COLUMN outlook_draft_id TEXT",
    "ALTER TABLE emails ADD COLUMN draft_pushed_at TEXT",
    "ALTER TABLE emails ADD COLUMN account_id TEXT",
    "CREATE INDEX IF NOT EXISTS idx_emails_account ON emails(account_id)",
    "ALTER TABLE emails ADD COLUMN body_translated TEXT",
    "ALTER TABLE attachments ADD COLUMN downloaded_to TEXT",
    "ALTER TABLE attachments ADD COLUMN outlook_attachment_id TEXT",
]


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    # Apply additive migrations idempotently. SQLite has no `IF NOT EXISTS` for
    # ALTER TABLE, so we swallow "duplicate column" errors.
    for stmt in _MIGRATIONS:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
    conn.commit()
    conn.close()
    print(f"Initialized DB at {DB_PATH}")


def wipe_demo():
    conn = get_conn()
    cur = conn.execute("SELECT COUNT(*) FROM emails WHERE is_demo = 1")
    n = cur.fetchone()[0]
    conn.execute("DELETE FROM emails WHERE is_demo = 1")
    conn.execute("DELETE FROM attachments WHERE is_demo = 1")
    conn.execute("DELETE FROM todos WHERE is_demo = 1")
    conn.commit()
    conn.close()
    print(f"Wiped {n} demo emails (and their attachments/todos).")


def wipe_all():
    conn = get_conn()
    conn.execute("DELETE FROM emails")
    conn.execute("DELETE FROM attachments")
    conn.execute("DELETE FROM todos")
    conn.commit()
    conn.close()
    print("Wiped all rows.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["init", "wipe-demo", "wipe-all"])
    args = parser.parse_args()
    actions = {"init": init_db, "wipe-demo": wipe_demo, "wipe-all": wipe_all}
    actions[args.action]()
