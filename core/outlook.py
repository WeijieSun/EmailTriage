"""Microsoft Graph client for Outlook integration. Multi-account aware.

- Auth: MSAL device-code flow (no callback URL needed). Token cached to
  data/.token_cache.json — supports multiple signed-in accounts in one cache.
- Reads .env from the project root for OUTLOOK_CLIENT_ID and OUTLOOK_TENANT_ID.
- All Graph wrappers accept an optional `account` parameter (email address).
  When omitted: uses the only signed-in account, or errors with helpful
  guidance if 0 or 2+ accounts are present.

CLI:
    python -m core.outlook login                      # add an account
    python -m core.outlook accounts                   # list signed-in accounts
    python -m core.outlook whoami [--account <email>]
    python -m core.outlook list   [--account <email>] --top 10
    python -m core.outlook push-drafts [--account <email> | --all-accounts]
    python -m core.outlook logout [--account <email>] # remove one or all
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOKEN_CACHE_PATH = PROJECT_ROOT / "data" / ".token_cache.json"
ENV_PATH = PROJECT_ROOT / ".env"

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["Mail.ReadWrite", "Mail.Send", "User.Read"]


# ---------------------------------------------------------------------------
# Lazy imports + config
# ---------------------------------------------------------------------------

def _require(module_name: str):
    try:
        return __import__(module_name)
    except ImportError as e:
        raise RuntimeError(
            f"Missing dependency '{module_name}'. Install with:  uv sync  (or: pip install msal requests python-dotenv)"
        ) from e


def _load_env() -> tuple[str, str]:
    try:
        from dotenv import load_dotenv
        if ENV_PATH.exists():
            load_dotenv(ENV_PATH)
    except ImportError:
        pass

    cid = os.environ.get("OUTLOOK_CLIENT_ID", "").strip()
    tid = os.environ.get("OUTLOOK_TENANT_ID", "common").strip() or "common"
    if not cid:
        raise RuntimeError(
            "OUTLOOK_CLIENT_ID is not set. Copy .env.example to .env and fill in your Azure App's client_id.\n"
            "See docs/outlook-setup.md for Azure App registration steps."
        )
    return cid, tid


# ---------------------------------------------------------------------------
# MSAL helpers (multi-account)
# ---------------------------------------------------------------------------

_app_cache = None


def _build_msal_app():
    global _app_cache
    if _app_cache is not None:
        return _app_cache
    msal = _require("msal")
    cid, tid = _load_env()
    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE_PATH.exists():
        cache.deserialize(TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
    _app_cache = msal.PublicClientApplication(
        cid,
        authority=f"https://login.microsoftonline.com/{tid}",
        token_cache=cache,
    )
    return _app_cache


def _save_cache(app) -> None:
    if app.token_cache.has_state_changed:
        TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE_PATH.write_text(app.token_cache.serialize(), encoding="utf-8")


def list_accounts() -> list[dict]:
    """Return list of signed-in accounts: [{username, home_account_id}]."""
    app = _build_msal_app()
    return [
        {"username": a["username"], "home_account_id": a["home_account_id"]}
        for a in app.get_accounts()
    ]


def _resolve_account(account: Optional[str], app) -> dict:
    """Resolve a user-supplied account hint to an MSAL account dict.

    - account=None + 0 signed-in: error
    - account=None + 1 signed-in: use it
    - account=None + 2+ signed-in: error with available list
    - account=email: match by username (case-insensitive)
    """
    accounts = app.get_accounts()
    if account:
        target = account.lower()
        for a in accounts:
            if a["username"].lower() == target:
                return a
        names = ", ".join(a["username"] for a in accounts) or "(none)"
        raise RuntimeError(
            f"Account '{account}' is not signed in. Available: {names}\n"
            f"Run: python -m core.outlook login   to add it."
        )
    if not accounts:
        raise RuntimeError(
            "No signed-in accounts. Run:  python -m core.outlook login"
        )
    if len(accounts) > 1:
        names = ", ".join(a["username"] for a in accounts)
        raise RuntimeError(
            f"Multiple accounts signed in ({names}). Specify with --account <email>, "
            f"or use --all-accounts where supported."
        )
    return accounts[0]


def acquire_token(account: Optional[str] = None, force_login: bool = False) -> str:
    """Get an access token for an account. force_login adds a new account."""
    app = _build_msal_app()

    if force_login:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Device flow failed: {json.dumps(flow, indent=2)}")
        print("\n" + flow["message"] + "\n", flush=True)
        result = app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(f"Auth failed: {result.get('error_description') or result}")
        _save_cache(app)
        return result["access_token"]

    acc = _resolve_account(account, app)
    result = app.acquire_token_silent(SCOPES, account=acc)
    if not result or "access_token" not in result:
        raise RuntimeError(
            f"Silent token acquisition failed for {acc['username']}. "
            f"Run:  python -m core.outlook login   to refresh."
        )
    _save_cache(app)
    return result["access_token"]


def logout(account: Optional[str] = None) -> None:
    """Remove a single account or wipe the whole cache (account=None for all)."""
    if account is None:
        if TOKEN_CACHE_PATH.exists():
            TOKEN_CACHE_PATH.unlink()
            print("Token cache cleared (all accounts).")
        else:
            print("No token cache to clear.")
        return

    app = _build_msal_app()
    acc = _resolve_account(account, app)
    app.remove_account(acc)
    _save_cache(app)
    print(f"Removed account: {acc['username']}")


# ---------------------------------------------------------------------------
# Graph REST wrappers (all account-aware)
# ---------------------------------------------------------------------------

def _headers(account: Optional[str] = None) -> dict:
    return {"Authorization": f"Bearer {acquire_token(account=account)}"}


def _get(url: str, params: Optional[dict] = None, account: Optional[str] = None) -> dict:
    requests = _require("requests")
    r = requests.get(url, headers=_headers(account), params=params or {})
    r.raise_for_status()
    return r.json()


def _post(url: str, json_body: Optional[dict] = None, account: Optional[str] = None) -> dict:
    requests = _require("requests")
    r = requests.post(
        url,
        headers={**_headers(account), "Content-Type": "application/json"},
        json=json_body or {},
    )
    r.raise_for_status()
    return r.json() if r.content else {}


def _patch(url: str, json_body: dict, account: Optional[str] = None) -> dict:
    requests = _require("requests")
    r = requests.patch(
        url,
        headers={**_headers(account), "Content-Type": "application/json"},
        json=json_body,
    )
    r.raise_for_status()
    return r.json() if r.content else {}


def me(account: Optional[str] = None) -> dict:
    return _get(f"{GRAPH_BASE}/me", account=account)


def list_inbox(top: int = 25, filter_: Optional[str] = None, folder: str = "Inbox", account: Optional[str] = None) -> list[dict]:
    url = f"{GRAPH_BASE}/me/mailFolders/{folder}/messages"
    params = {
        "$top": top,
        "$orderby": "receivedDateTime desc",
        "$select": "id,subject,from,receivedDateTime,bodyPreview,body,hasAttachments,isRead,conversationId",
    }
    if filter_:
        params["$filter"] = filter_
    return _get(url, params, account=account).get("value", [])


def get_message(message_id: str, account: Optional[str] = None) -> dict:
    return _get(f"{GRAPH_BASE}/me/messages/{message_id}", account=account)


def list_attachments(message_id: str, account: Optional[str] = None) -> list[dict]:
    return _get(f"{GRAPH_BASE}/me/messages/{message_id}/attachments", account=account).get("value", [])


def download_attachment(message_id: str, attachment_id: str, save_path: Path, account: Optional[str] = None) -> Path:
    requests = _require("requests")
    url = f"{GRAPH_BASE}/me/messages/{message_id}/attachments/{attachment_id}/$value"
    r = requests.get(url, headers=_headers(account))
    r.raise_for_status()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(r.content)
    return save_path


def create_draft_reply(message_id: str, body: str, content_type: str = "text", account: Optional[str] = None) -> dict:
    draft = _post(f"{GRAPH_BASE}/me/messages/{message_id}/createReply", account=account)
    draft_id = draft["id"]
    # PATCH may return empty body — always use the createReply id, not the PATCH response
    _patch(
        f"{GRAPH_BASE}/me/messages/{draft_id}",
        {"body": {"contentType": content_type, "content": body}},
        account=account,
    )
    return {"id": draft_id}


def delete_message(message_id: str, account: Optional[str] = None) -> None:
    """Permanently delete a message/draft from Outlook by its Graph message ID."""
    requests = _require("requests")
    r = requests.delete(
        f"{GRAPH_BASE}/me/messages/{message_id}",
        headers=_headers(account),
    )
    if r.status_code not in (204, 404):
        r.raise_for_status()


def find_and_delete_draft_by_subject(subject: str, account: Optional[str] = None) -> bool:
    """Search Drafts folder for a message matching subject and delete it. Returns True if deleted."""
    search_subject = subject if not subject.startswith("RE: ") else subject
    re_subject = subject if subject.startswith("RE: ") else f"RE: {subject}"
    try:
        msgs = _get(
            f"{GRAPH_BASE}/me/mailFolders/Drafts/messages",
            params={"$select": "id,subject", "$top": 50},
            account=account,
        ).get("value", [])
        for m in msgs:
            if m.get("subject", "") in (search_subject, re_subject):
                delete_message(m["id"], account=account)
                return True
    except Exception:
        pass
    return False


def create_draft(to: str, subject: str, body: str, content_type: str = "text", account: Optional[str] = None) -> dict:
    return _post(
        f"{GRAPH_BASE}/me/messages",
        {
            "subject": subject,
            "body": {"contentType": content_type, "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}],
        },
        account=account,
    )


# ---------------------------------------------------------------------------
# DB integration: push DB drafts. Filters by account_id when provided.
# ---------------------------------------------------------------------------

def push_pending_drafts(account: Optional[str] = None, all_accounts: bool = False, dry_run: bool = False) -> int:
    """Push DB rows with draft_text + no Outlook draft yet.

    - all_accounts=True: fan out per-account, calling Graph using each row's account_id
    - account=email: only push that account's rows
    - account=None and not all_accounts: only valid if exactly one account is signed in
    """
    from .db import get_conn

    if all_accounts:
        accounts_in_db = [r[0] for r in _distinct_accounts() if r[0]]
        if not accounts_in_db:
            print("No accounts found in DB. Run ingest first.")
            return 0
        total = 0
        for acc in accounts_in_db:
            print(f"\n--- account: {acc} ---")
            total += _push_drafts_for(acc, dry_run)
        return total

    # Resolve target account: explicit, or fall back to single signed-in
    if account is None:
        # If only one account signed in, use it; else error
        try:
            acc = _resolve_account(None, _build_msal_app())["username"]
        except RuntimeError as e:
            raise RuntimeError(str(e) + "\nOr re-run with --all-accounts to push for every DB account.") from e
        return _push_drafts_for(acc, dry_run)

    return _push_drafts_for(account, dry_run)


def _distinct_accounts() -> list[tuple]:
    from .db import get_conn
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT account_id FROM emails WHERE account_id IS NOT NULL AND is_demo = 0"
    ).fetchall()
    conn.close()
    return [tuple(r) for r in rows]


def _push_drafts_for(account: str, dry_run: bool) -> int:
    from .db import get_conn

    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id, message_id, from_addr, subject, draft_text, account_id
        FROM emails
        WHERE draft_text IS NOT NULL AND draft_text != ''
          AND outlook_draft_id IS NULL
          AND is_demo = 0
          AND account_id = ?
          AND status IN ('drafted', 'completed')
        """,
        (account,),
    ).fetchall()

    if not rows:
        conn.close()
        print(f"  No pending drafts for {account}.")
        return 0

    pushed = 0
    for r in rows:
        if dry_run:
            print(f"  [dry-run] would push #{r['id']} ({r['subject']}) for {account}")
            continue
        try:
            draft = create_draft_reply(r["message_id"], r["draft_text"], account=account)
            conn.execute(
                "UPDATE emails SET outlook_draft_id = ?, draft_pushed_at = datetime('now') WHERE id = ?",
                (draft.get("id"), int(r["id"])),
            )
            pushed += 1
            print(f"  pushed #{r['id']} ({account})")
        except Exception as e:
            print(f"  FAILED #{r['id']} ({account}): {e}", file=sys.stderr)

    conn.commit()
    conn.close()
    print(f"  {account}: pushed {pushed} draft(s).")
    return pushed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(description="Outlook integration via Microsoft Graph (multi-account).")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("login", help="Add a signed-in account via device-code flow")
    p_logout = sub.add_parser("logout", help="Remove an account or all (default: all)")
    p_logout.add_argument("--account", help="Email of account to remove (omit for all)")

    sub.add_parser("accounts", help="List signed-in accounts")

    p_who = sub.add_parser("whoami", help="Show authenticated account")
    p_who.add_argument("--account", help="Specific account email (default: only one signed in)")

    p_list = sub.add_parser("list", help="List recent inbox messages")
    p_list.add_argument("--account", help="Account to query (required if multiple signed in)")
    p_list.add_argument("--top", type=int, default=10)
    p_list.add_argument("--unread-only", action="store_true")

    p_push = sub.add_parser("push-drafts", help="Push DB drafts to Outlook drafts folder")
    grp = p_push.add_mutually_exclusive_group()
    grp.add_argument("--account", help="Push only this account's drafts")
    grp.add_argument("--all-accounts", action="store_true", help="Push for every account that has DB rows")
    p_push.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    try:
        if args.action == "login":
            acquire_token(force_login=True)
            # After login, MSAL added the new account. Show whoami for it.
            accounts = list_accounts()
            if accounts:
                latest = accounts[-1]["username"]
                info = me(account=latest)
                print(f"Logged in as: {info.get('userPrincipalName') or info.get('mail')}")
        elif args.action == "logout":
            logout(account=args.account)
        elif args.action == "accounts":
            accs = list_accounts()
            if not accs:
                print("(no signed-in accounts)")
            else:
                print(f"{'#':>3}  {'username':40s}  home_account_id")
                for i, a in enumerate(accs, 1):
                    print(f"{i:>3}  {a['username']:40s}  {a['home_account_id'][:24]}...")
        elif args.action == "whoami":
            info = me(account=args.account)
            print(json.dumps(
                {
                    "displayName": info.get("displayName"),
                    "userPrincipalName": info.get("userPrincipalName"),
                    "mail": info.get("mail"),
                    "id": info.get("id"),
                },
                indent=2,
            ))
        elif args.action == "list":
            f = "isRead eq false" if args.unread_only else None
            msgs = list_inbox(top=args.top, filter_=f, account=args.account)
            for m in msgs:
                sender = m.get("from", {}).get("emailAddress", {}).get("address", "?")
                unread = "🆕" if not m.get("isRead") else "  "
                print(f"{unread} {m['receivedDateTime']:25s}  {sender:35s}  {m.get('subject', '')}")
        elif args.action == "push-drafts":
            push_pending_drafts(
                account=args.account,
                all_accounts=args.all_accounts,
                dry_run=args.dry_run,
            )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
