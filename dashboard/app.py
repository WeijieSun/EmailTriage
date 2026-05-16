"""Email Triage Dashboard — Streamlit.

Reads/writes the same SQLite DB as the Claude skill, so any work the agent does
is reflected here on next refresh, and any user action here is visible to the agent.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import DB_PATH, get_conn, wipe_demo  # noqa: E402
from core.classifier import load_categories, get_category, render_draft  # noqa: E402
from core.i18n import t, cat_name, cat_template, email_summary, todo_text, LANGS  # noqa: E402
from core.process import process_new  # noqa: E402
from core.ingest import simulate as simulate_new  # noqa: E402

@st.cache_resource
def _init_chat_server():
    """Start chat API server once per Streamlit process."""
    try:
        from core.chat_api import start_chat_server
        start_chat_server(port=8502)
        return True
    except Exception:
        return False

_init_chat_server()


# Stable color per account so chips look consistent across renders.
_ACCOUNT_PALETTE = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"]


def _account_color(account_id: str | None) -> str:
    if not account_id:
        return "#94a3b8"
    return _ACCOUNT_PALETTE[hash(account_id) % len(_ACCOUNT_PALETTE)]


def _account_chip(account_id: str | None) -> str:
    """Return a small inline HTML chip for the account label."""
    if not account_id:
        return ""
    color = _account_color(account_id)
    return (
        f"<span style='background:{color};color:white;padding:1px 8px;border-radius:8px;"
        f"font-size:0.75em;font-weight:500;'>{account_id}</span>"
    )


st.set_page_config(page_title="Email Triage", page_icon="📧", layout="wide")

# ── Global Design System ─────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Fonts & Base ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── App Background ── */
.stApp {
    background: #f0f4f8;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #161b22 60%, #0d1117 100%) !important;
    border-right: 1px solid rgba(99,102,241,0.25) !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.5rem;
}
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #94a3b8 !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    margin-bottom: 0.75rem !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div {
    color: #cbd5e1 !important;
}
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stCheckbox label {
    color: #e2e8f0 !important;
    font-size: 0.88rem !important;
}
[data-testid="stSidebar"] hr {
    border-color: rgba(99,102,241,0.2) !important;
    margin: 1rem 0 !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(99,102,241,0.3) !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(99,102,241,0.2) !important;
    border-radius: 10px !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    color: #f87171 !important;
    font-size: 0.85rem !important;
}

/* ── Main area container ── */
.main .block-container {
    padding: 2rem 2.5rem 3rem !important;
    max-width: 1400px !important;
}

/* ── Title ── */
h1 {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #06b6d4 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 700 !important;
    font-size: 2rem !important;
    letter-spacing: -0.03em !important;
}

/* ── Metric Cards ── */
[data-testid="stMetric"] {
    background: #ffffff !important;
    border-radius: 14px !important;
    padding: 1.4rem 1.6rem !important;
    border: 1px solid rgba(0,0,0,0.06) !important;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05), 0 0 0 1px rgba(99,102,241,0.04) !important;
    border-top: 3px solid #6366f1 !important;
    transition: transform 0.2s, box-shadow 0.2s !important;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(99,102,241,0.12) !important;
}
[data-testid="stMetricLabel"] {
    color: #64748b !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
[data-testid="stMetricValue"] {
    color: #0f172a !important;
    font-size: 2.4rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}

/* ── Buttons ── */
[data-testid="stButton"] > button {
    border-radius: 10px !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    padding: 0.55rem 1.2rem !important;
    border: 1px solid rgba(0,0,0,0.08) !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.01em !important;
}
[data-testid="stButton"] > button[kind="primary"],
[data-testid="stButton"] > button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
    color: white !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(99,102,241,0.35) !important;
}
[data-testid="stButton"] > button[kind="primary"]:hover {
    box-shadow: 0 6px 20px rgba(99,102,241,0.5) !important;
    transform: translateY(-1px) !important;
}
[data-testid="stButton"] > button[kind="secondary"]:hover {
    background: #f1f5f9 !important;
    border-color: #6366f1 !important;
    color: #6366f1 !important;
}

/* ── Tabs ── */
[role="tablist"] {
    background: transparent !important;
    border-bottom: 2px solid #e2e8f0 !important;
    gap: 0 !important;
    padding-bottom: 0 !important;
}
[role="tab"] {
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    margin-bottom: -2px !important;
    color: #64748b !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    padding: 0.6rem 1rem !important;
    border-radius: 0 !important;
    transition: all 0.2s !important;
}
[role="tab"]:hover {
    color: #6366f1 !important;
    background: rgba(99,102,241,0.05) !important;
}
[role="tab"][aria-selected="true"] {
    color: #6366f1 !important;
    border-bottom: 2px solid #6366f1 !important;
    font-weight: 600 !important;
}

/* ── Expanders (Email cards) ── */
[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid rgba(0,0,0,0.07) !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.04) !important;
    overflow: hidden !important;
    margin-bottom: 0.6rem !important;
    transition: box-shadow 0.2s !important;
}
[data-testid="stExpander"]:hover {
    box-shadow: 0 4px 16px rgba(99,102,241,0.1) !important;
}
[data-testid="stExpander"] summary {
    padding: 0.9rem 1.2rem !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    color: #1e293b !important;
}
[data-testid="stExpander"] summary:hover {
    background: rgba(99,102,241,0.03) !important;
}
[data-testid="stExpander"] > div:last-child {
    border-top: 1px solid rgba(0,0,0,0.05) !important;
}

/* ── Alerts / Banners ── */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    border: none !important;
    font-size: 0.875rem !important;
}
[data-testid="stAlert"][data-baseweb="notification"] {
    background: rgba(99,102,241,0.06) !important;
    border-left: 4px solid #6366f1 !important;
}

/* ── Success / Warning banners ── */
div[class*="stSuccess"] {
    background: rgba(16,185,129,0.08) !important;
    border: 1px solid rgba(16,185,129,0.25) !important;
    border-radius: 12px !important;
    color: #065f46 !important;
}
div[class*="stWarning"] {
    background: rgba(245,158,11,0.08) !important;
    border: 1px solid rgba(245,158,11,0.25) !important;
    border-radius: 12px !important;
}

/* ── Progress bars ── */
[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg, #6366f1, #8b5cf6) !important;
    border-radius: 999px !important;
}
[data-testid="stProgress"] > div {
    background: #e2e8f0 !important;
    border-radius: 999px !important;
    height: 6px !important;
}

/* ── Text inputs ── */
[data-testid="stTextInput"] input,
[data-testid="stDateInput"] input {
    border-radius: 9px !important;
    border: 1.5px solid #e2e8f0 !important;
    font-size: 0.875rem !important;
    padding: 0.55rem 0.9rem !important;
    transition: border-color 0.2s !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stDateInput"] input:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important;
}

/* ── Text areas ── */
textarea {
    border-radius: 9px !important;
    border: 1.5px solid #e2e8f0 !important;
    font-size: 0.875rem !important;
    transition: border-color 0.2s !important;
}
textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important;
}

/* ── Info boxes (summaries) ── */
[data-testid="stInfo"] {
    background: linear-gradient(135deg, rgba(6,182,212,0.07), rgba(99,102,241,0.07)) !important;
    border: 1px solid rgba(6,182,212,0.25) !important;
    border-radius: 10px !important;
    color: #0e7490 !important;
}

/* ── Multiselect / Select tags ── */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: rgba(99,102,241,0.12) !important;
    color: #6366f1 !important;
    border-radius: 999px !important;
    border: none !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
}
/* Sidebar multiselect input text — must be dark on white dropdown bg */
[data-testid="stSidebar"] [data-testid="stMultiSelect"] input,
[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="input"] input {
    color: #1e293b !important;
}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] {
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(99,102,241,0.3) !important;
    border-radius: 9px !important;
}
/* Dropdown menu items */
[data-testid="stSidebar"] li[role="option"] {
    color: #1e293b !important;
    background: white !important;
}
[data-testid="stSidebar"] li[role="option"]:hover {
    background: rgba(99,102,241,0.08) !important;
}
/* Tags in sidebar multiselect */
[data-testid="stSidebar"] [data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: rgba(99,102,241,0.85) !important;
    color: white !important;
}

/* ── Checkboxes ── */
[data-testid="stCheckbox"] span[aria-checked="true"] {
    background: #6366f1 !important;
    border-color: #6366f1 !important;
}

/* ── Dividers ── */
hr {
    border-color: rgba(0,0,0,0.06) !important;
    margin: 1.5rem 0 !important;
}

/* ── Spinner ── */
[data-testid="stSpinner"] {
    color: #6366f1 !important;
}

/* ── JSON display ── */
[data-testid="stJson"] {
    border-radius: 10px !important;
    border: 1px solid rgba(0,0,0,0.07) !important;
    background: #f8fafc !important;
}

/* ── Toast notifications ── */
[data-testid="stToast"] {
    border-radius: 12px !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.12) !important;
    border: 1px solid rgba(0,0,0,0.06) !important;
}

/* ── Containers with border ── */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px !important;
    border: 1px solid rgba(0,0,0,0.07) !important;
    background: #ffffff !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.04) !important;
}

/* ── Caption text ── */
.stCaption, [data-testid="stCaptionContainer"] {
    color: #94a3b8 !important;
    font-size: 0.78rem !important;
}

/* ── Code/mono text ── */
code {
    background: rgba(99,102,241,0.08) !important;
    color: #6366f1 !important;
    border-radius: 5px !important;
    padding: 0.1em 0.4em !important;
    font-size: 0.85em !important;
}

/* ── Scrollbars ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: #6366f1; }
</style>
""", unsafe_allow_html=True)


# ----------------- DB helpers -----------------

@st.cache_data(ttl=2)
def load_emails(data_filter: str, account_filter: tuple[str, ...] | None = None):
    conn = get_conn()
    where_clauses = []
    params: list = []
    if data_filter == "demo":
        where_clauses.append("is_demo = 1")
    elif data_filter == "real":
        where_clauses.append("is_demo = 0")
    if account_filter:
        placeholders = ",".join("?" * len(account_filter))
        where_clauses.append(f"account_id IN ({placeholders})")
        params.extend(account_filter)
    where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    df = pd.read_sql(f"SELECT * FROM emails {where} ORDER BY received_at DESC", conn, params=params)
    conn.close()
    return df


@st.cache_data(ttl=5)
def load_distinct_accounts():
    conn = get_conn()
    df = pd.read_sql(
        "SELECT account_id, COUNT(*) AS n FROM emails WHERE account_id IS NOT NULL GROUP BY account_id ORDER BY account_id",
        conn,
    )
    conn.close()
    return df


@st.cache_data(ttl=2)
def load_attachments(email_id: int):
    conn = get_conn()
    df = pd.read_sql(
        "SELECT * FROM attachments WHERE email_id = ?", conn, params=(email_id,)
    )
    conn.close()
    return df


@st.cache_data(ttl=2)
def load_todos(data_filter: str):
    conn = get_conn()
    where = ""
    if data_filter == "demo":
        where = "WHERE is_demo = 1"
    elif data_filter == "real":
        where = "WHERE is_demo = 0"
    df = pd.read_sql(f"SELECT * FROM todos {where} ORDER BY created_at DESC", conn)
    conn.close()
    return df


def write_status(email_id: int, status: str):
    conn = get_conn()
    conn.execute("UPDATE emails SET status = ?, processed_at = datetime('now') WHERE id = ?", (status, email_id))
    conn.commit()
    conn.close()
    st.cache_data.clear()


def write_draft(email_id: int, draft_text: str):
    conn = get_conn()
    conn.execute(
        "UPDATE emails SET draft_text = ?, status = CASE WHEN status = 'new' THEN 'drafted' ELSE status END WHERE id = ?",
        (draft_text, email_id),
    )
    conn.commit()
    conn.close()
    st.cache_data.clear()


def write_translation(email_id: int, text: str):
    conn = get_conn()
    conn.execute("UPDATE emails SET body_translated = ? WHERE id = ?", (text, email_id))
    conn.commit()
    conn.close()
    st.cache_data.clear()


def write_summary(email_id: int, summary_zh: str, summary_en: str):
    conn = get_conn()
    conn.execute("UPDATE emails SET summary = ?, summary_en = ? WHERE id = ?", (summary_zh, summary_en, email_id))
    conn.commit()
    conn.close()
    st.cache_data.clear()


def write_attachment_downloaded(att_id: int, path: str):
    conn = get_conn()
    conn.execute("UPDATE attachments SET downloaded_to = ? WHERE id = ?", (path, att_id))
    conn.commit()
    conn.close()
    st.cache_data.clear()


CHAT_FILE = Path(DB_PATH).parent / "chat_history.json"


def clean_body(text: str, max_len: int = 2000) -> str:
    import re
    if not isinstance(text, str):
        return ""
    text = text.replace("â€™", "'").replace("â€œ", '"').replace("â€", '"')
    text = text.replace("�", " ")
    text = re.sub(r"\?{3,}", " ", text)
    # Strip Windows/Unix paths but keep filename only
    text = re.sub(r"[A-Za-z]:\\(?:[^\s\\]+\\)*([^\s\\\n]+)", r"\1", text)
    text = re.sub(r"/(?:[^\s/\n]+/)+([^\s/\n]+)", r"\1", text)
    text = re.sub(r"[^\x09\x0a\x0d\x20-\x7e一-鿿　-〿＀-￯]", " ", text)
    text = re.sub(r" {3,}", " ", text)
    text = re.sub(r"\n{4,}", "\n\n", text)
    return text.strip()[:max_len]


def load_chat_history() -> list[dict]:
    if CHAT_FILE.exists():
        try:
            return json.loads(CHAT_FILE.read_text(encoding="utf-8"))[-100:]
        except Exception:
            pass
    return []


def save_chat_history(msgs: list[dict]) -> None:
    try:
        CHAT_FILE.write_text(json.dumps(msgs[-100:], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _find_claude() -> str:
    import glob as _glob
    candidates = [
        shutil.which("claude"),
        os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd"),
        os.path.join(os.environ.get("APPDATA", ""), "npm", "claude"),
    ]
    # VS Code extension ships claude.exe — discover any installed version
    vscode_pattern = os.path.join(
        os.environ.get("USERPROFILE", ""),
        ".vscode", "extensions", "anthropic.claude-code-*",
        "resources", "native-binary", "claude.exe",
    )
    candidates.extend(_glob.glob(vscode_pattern))
    for c in candidates:
        if c and Path(c).exists():
            return c
    return "claude"


def call_claude(prompt: str, timeout: int = 120) -> tuple[str | None, str]:
    """Call claude --print via a temp file. Returns (result, error_msg)."""
    import tempfile, os as _os
    claude_bin = _find_claude()
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8-sig") as f:
            f.write(prompt)
            tmp = f.name
        import tempfile as _tf
        ps_cmd = (
            f"$OutputEncoding = [System.Text.Encoding]::UTF8; "
            f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            f"Get-Content -Raw -Encoding UTF8 '{tmp}' | & '{claude_bin}' --print"
        )
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=timeout, encoding="utf-8",
            cwd=_tf.gettempdir(),  # run outside project dir to avoid CLAUDE.md context
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip(), ""
        err = (result.stderr or "").strip()[:300] or f"returncode={result.returncode}"
        return None, err
    except subprocess.TimeoutExpired:
        return None, f"超时（>{timeout}s）"
    except Exception as e:
        return None, str(e)
    finally:
        if tmp and _os.path.exists(tmp):
            try: _os.unlink(tmp)
            except Exception: pass


def detect_email_lang(subject: str, body: str) -> str:
    """Return 'zh' if email is predominantly Chinese, else 'en'."""
    text = f"{subject} {body}"
    if not text.strip():
        return "en"
    chinese = sum(1 for c in text if "一" <= c <= "鿿")
    return "zh" if chinese / max(len(text), 1) > 0.08 else "en"




def pick_folder() -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        folder = filedialog.askdirectory(title="选择 STL 文件保存目录")
        root.destroy()
        return folder or None
    except Exception:
        return None


def write_todo_status(todo_id: int, status: str):
    conn = get_conn()
    completed = "datetime('now')" if status == "done" else "NULL"
    conn.execute(f"UPDATE todos SET status = ?, completed_at = {completed} WHERE id = ?", (status, todo_id))
    conn.commit()
    conn.close()
    st.cache_data.clear()


# ----------------- Sidebar (language + filters + actions) -----------------

with st.sidebar:
    st.markdown("### 🌐 Language / 语言")
    lang_keys = list(LANGS.keys())
    default_idx = lang_keys.index(st.session_state.get("lang", "zh"))
    lang = st.radio(
        " ",
        lang_keys,
        index=default_idx,
        format_func=lambda k: LANGS[k],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.session_state["lang"] = lang

    st.divider()
    st.markdown(f"### {t('filters', lang)}")

    data_filter = st.radio(
        t("data_source", lang),
        ["all", "demo", "real"],
        format_func=lambda v: {"all": t("data_all", lang), "demo": t("data_demo", lang), "real": t("data_real", lang)}[v],
        horizontal=True,
    )

    accounts_df = load_distinct_accounts()
    if len(accounts_df) > 0:
        all_accounts = accounts_df["account_id"].tolist()
        account_options = ["__all__"] + all_accounts
        sel = st.multiselect(
            t("account_filter", lang),
            options=account_options,
            default=["__all__"],
            format_func=lambda v: t("all_accounts", lang) if v == "__all__" else f"{v} ({int(accounts_df.loc[accounts_df['account_id']==v, 'n'].values[0])})",
        )
        if "__all__" in sel or not sel:
            account_filter: tuple[str, ...] | None = None
        else:
            account_filter = tuple(sel)
    else:
        account_filter = None

    status_filter = st.selectbox(
        t("filter_status", lang),
        ["all", "new", "drafted", "completed"],
        format_func=lambda v: {
            "all": t("filter_all", lang),
            "new": t("status_new", lang),
            "drafted": t("status_drafted", lang),
            "completed": t("status_completed", lang),
        }[v],
    )

    auto_refresh = st.checkbox(t("auto_refresh", lang), value=False)

    st.divider()
    st.markdown(f"### {t('settings', lang)}")
    st.caption(f"{t('footer_db', lang)}: `{DB_PATH}`")

    with st.expander(t("wipe_demo", lang)):
        st.warning(t("wipe_demo_confirm", lang))
        if st.button(t("wipe_demo", lang), type="primary"):
            wipe_demo()
            st.cache_data.clear()
            st.success(t("wipe_demo_done", lang))
            st.rerun()



if auto_refresh:
    st.markdown('<meta http-equiv="refresh" content="60">', unsafe_allow_html=True)


# ----------------- Header / metrics -----------------

st.title(t("app_title", lang))

emails = load_emails(data_filter, account_filter)
todos = load_todos(data_filter)

if status_filter != "all":
    emails_view = emails[emails["status"] == status_filter]
else:
    emails_view = emails

c1, c2, c3, c4 = st.columns(4)
c1.metric(t("metric_total", lang), len(emails))
c2.metric(t("metric_new", lang), int((emails["status"] == "new").sum()))
c3.metric(t("metric_drafted", lang), int((emails["status"] == "drafted").sum()))
c4.metric(t("metric_completed", lang), int((emails["status"] == "completed").sum()))

n_new = int((emails["status"] == "new").sum())
last_processed = emails["processed_at"].dropna().max() if "processed_at" in emails.columns and len(emails) else None
ca, cb = st.columns([3, 2])
with ca:
    if n_new > 0:
        st.warning(t("unprocessed_alert", lang, n=n_new))
    else:
        st.success(t("unprocessed_none", lang))
with cb:
    st.caption(f"{t('last_processed', lang)}: {last_processed or t('never', lang)}")

import datetime as _dt
_today = _dt.date.today()
_fc1, _fc2, _fc3 = st.columns([2, 2, 1])
with _fc1:
    fetch_since = st.date_input("拉取起始日期", value=_today, key="fetch_since_date", label_visibility="collapsed")
with _fc2:
    fetch_until = st.date_input("拉取结束日期", value=_today, key="fetch_until_date", label_visibility="collapsed")
with _fc3:
    if st.button("🔄 拉取新邮件", use_container_width=True, key="fetch_new_btn"):
        with st.spinner("拉取中…"):
            try:
                from core.ingest import ingest_outlook
                since_iso = f"{fetch_since.isoformat()}T00:00:00Z"
                fetched = ingest_outlook(top=200, since=since_iso, all_accounts=True)
                st.cache_data.clear()
                st.toast(f"拉取完成，新增 {fetched} 封", icon="📬")
                st.rerun()
            except Exception as e:
                st.error(f"拉取失败: {e}")


# ----------------- One-click daily action -----------------

with st.container(border=True):
    cols = st.columns([2, 2, 2, 3])
    cols[0].markdown(f"### {t('daily_actions', lang)}")
    cols[1].caption(t("daily_run", lang))

    source_mode = cols[2].radio(
        t("daily_pull_source", lang),
        ["outlook", "simulate"],
        format_func=lambda v: t("source_outlook", lang) if v == "outlook" else t("source_simulate", lang),
        horizontal=True,
        key="daily_source_mode",
        label_visibility="collapsed",
    )

    if cols[3].button(t("daily_actions", lang), type="primary", use_container_width=True, key="daily_run_btn"):
        progress = st.progress(0, text=t("daily_step_fetch", lang))
        fetched = processed = pushed = 0

        # Step 1: fetch
        if source_mode == "simulate":
            try:
                simulate_new(n=3)
                fetched = 3
            except Exception as e:
                st.error(f"simulate failed: {e}")
        else:
            try:
                from core.ingest import ingest_outlook
                fetched = ingest_outlook(top=50, unread_only=True, all_accounts=True)
            except Exception as e:
                st.error(f"Outlook fetch failed: {e}")

        progress.progress(33, text=t("daily_step_process", lang))

        # Step 2: process each non-spam email one by one with real progress
        try:
            from core.db import get_conn as _gc2
            import re as _re
            _conn2 = _gc2()
            _new_rows = _conn2.execute("SELECT * FROM emails WHERE status='new' ORDER BY id").fetchall()
            _conn2.close()

            _actionable = [r for r in _new_rows if (r["category"] or "other") != "spam"]
            _spam_rows  = [r for r in _new_rows if (r["category"] or "other") == "spam"]

            # Mark spam as completed silently
            if _spam_rows:
                _c = _gc2()
                for _s in _spam_rows:
                    _c.execute("UPDATE emails SET status='completed', processed_at=datetime('now') WHERE id=?", (int(_s["id"]),))
                _c.commit(); _c.close()
                processed += len(_spam_rows)

            _total = len(_actionable)
            for _i, _em in enumerate(_actionable):
                _pct = 33 + int((_i / max(_total, 1)) * 55)
                _subj = str(_em["subject"] or "(no subject)")
                _frm  = str(_em["from_addr"] or "")
                _body = _em["body"] if isinstance(_em["body"], str) else ""
                _is_demo = bool(_em["is_demo"])
                progress.progress(_pct, text=f"({_i+1}/{_total}) 起草：{_subj[:40]}")

                # All emails go through Claude
                _zh_count = sum(1 for c in (_subj + _body) if "一" <= c <= "鿿")
                _use_zh = (_zh_count / max(len(_subj + _body), 1)) > 0.15
                _rl = "Chinese (简体中文)" if _use_zh else "English"
                _prompt = (
                    f"[邮件原文开始]\nFrom: {_frm}\nSubject: {_subj}\n\n{_body[:1500]}\n[邮件原文结束]\n\n"
                    f"以上邮件的专业回复（{_rl}，只写回复正文）："
                )
                _draft, _ = call_claude(_prompt, timeout=90)
                _draft = _draft or ""

                # Save to DB
                _c = _gc2()
                _c.execute(
                    "UPDATE emails SET draft_text=?, status='drafted', processed_at=datetime('now') WHERE id=?",
                    (_draft, int(_em["id"]))
                )
                _c.commit(); _c.close()
                processed += 1

                # Push to Outlook — real emails only
                if not _is_demo and source_mode == "outlook" and _draft and _em["message_id"] and not _em["outlook_draft_id"]:
                    try:
                        from core.outlook import create_draft_reply as _cdr
                        _d_obj = _cdr(_em["message_id"], _draft, account=_em["account_id"])
                        _c2 = _gc2()
                        _c2.execute(
                            "UPDATE emails SET outlook_draft_id=?, draft_pushed_at=datetime('now') WHERE id=?",
                            (_d_obj.get("id"), int(_em["id"]))
                        )
                        _c2.commit(); _c2.close()
                        pushed += 1
                    except Exception:
                        pass

        except Exception as e:
            st.error(f"process failed: {e}")

        if source_mode != "outlook":
            st.info(t("daily_demo_mode", lang))

        progress.progress(100, text=t("daily_done", lang, f=fetched, p=processed, d=pushed))
        st.success(t("daily_done", lang, f=fetched, p=processed, d=pushed))
        st.cache_data.clear()
        st.rerun()

st.divider()


# ----------------- To-Dos panel -----------------

_todo_hdr_col, _todo_btn_col = st.columns([4, 1])
with _todo_hdr_col:
    _todo_label = f"{t('todos_section', lang)} ({int((todos['status'] == 'pending').sum())} {t('todo_pending', lang)})"
with _todo_btn_col:
    if st.button("🤖 Claude 整理", key="claude_todo_btn", use_container_width=True):
        with st.spinner("Claude 分析待处理邮件…"):
            st.cache_data.clear()
            _fresh = load_emails(data_filter, account_filter)
            # Only include 'new' status — drafted emails already have action taken
            _unprocessed = _fresh[
                (_fresh["status"] == "new") &
                (_fresh["category"] != "spam")
            ]
            if len(_unprocessed) == 0:
                st.toast("没有待处理的新邮件", icon="✅")
            else:
                from core.classifier import get_category as _gc_todo
                import re as _re_todo
                _lines = []
                for _, _em in _unprocessed.iterrows():
                    _cat_id = str(_em.get("category") or "other")
                    _cat_zh = _gc_todo(_cat_id).get("name", _cat_id)
                    _subj = str(_em.get("subject") or "(无主题)")
                    _frm = str(_em.get("from_addr") or "")
                    _summ = email_summary(_em, "zh")
                    _body_raw = _em.get("body")
                    _body_preview = _body_raw[:150] if isinstance(_body_raw, str) else ""
                    _detail = _summ or _body_preview
                    _lines.append("- 分类：%s | 发件人：%s | 主题：%s | 正文摘要：%s" % (
                        _cat_zh, _frm, _subj, _detail[:120] if _detail else "(无)"
                    ))
                _email_list = "\n".join(_lines)
                if lang == "en":
                    _prompt = (
                        "Based on the following emails, generate a specific actionable to-do list in English.\n"
                        "Rules:\n"
                        "- Format for unique tasks: '• SenderName - specific action needed'\n"
                        "- Only group emails if they require the EXACT same action (e.g. multiple people all requesting an invoice). "
                        "  In that case format as: '• Action needed: Person1, Person2, Person3'\n"
                        "- Keep specific details: clinic name, patient ID, invoice number, amount, tracking number, dates\n"
                        "- Each item starts with '• ', one per line, no sub-bullets\n"
                        "- Output ONLY the list, no preamble, no explanation\n\n"
                        "Emails:\n%s"
                    ) % _email_list
                else:
                    _prompt = (
                        "请根据以下邮件列表，生成一份具体可执行的中文待办事项清单。\n"
                        "格式规则：\n"
                        "- 独立事项格式：「• 发件人 - 具体要做的事」\n"
                        "- 只有完全相同的事情才合并（例如多人都要求开发票），合并格式：「• 需要做的事：人1、人2、人3」\n"
                        "- 保留具体细节：诊所名、患者号、发票号、金额、追踪号、日期等\n"
                        "- 每条以「• 」开头，一行一条，不要子项\n"
                        "- 只输出待办列表，不要任何前言或解释\n\n"
                        "邮件列表：\n%s"
                    ) % _email_list
                _result, _err = call_claude(_prompt, timeout=300)
                if _result:
                    _items = []
                    for _line in _result.splitlines():
                        _stripped = _line.strip()
                        if not _stripped:
                            continue
                        # Accept •·-* at any indent level
                        if _stripped[0] in "•·-*":
                            _content = _stripped.lstrip("•·-* ").strip()
                            _content = _re_todo.sub(r"^\[.*?\]\s*", "", _content).strip()
                            if _content and len(_content) > 2:
                                _items.append(_content)
                    # Fallback: if no bullet lines found, split by newline and take non-empty lines
                    if not _items:
                        _items = [l.strip() for l in _result.splitlines()
                                  if l.strip() and len(l.strip()) > 3 and not l.strip().startswith("#")]
                    if _items:
                        _now = __import__("datetime").datetime.now().isoformat(timespec="seconds")
                        _conn_t = get_conn()
                        # Clear ALL pending todos (demo + non-demo) to avoid duplicates
                        _conn_t.execute("DELETE FROM todos WHERE status='pending'")
                        for _item in _items:
                            _desc_zh = _item if lang == "zh" else ""
                            _desc_en = _item if lang == "en" else ""
                            _conn_t.execute(
                                "INSERT INTO todos (email_id, description, description_en, status, created_at, is_demo) VALUES (NULL,?,?,?,?,0)",
                                (_desc_zh or _item, _desc_en or _item, "pending", _now)
                            )
                        _conn_t.commit()
                        _conn_t.close()
                        st.cache_data.clear()
                        st.session_state["todos_open"] = True
                        st.toast(f"已生成 {len(_items)} 条待办", icon="🤖")
                        st.rerun()
                    else:
                        st.error(f"Claude 返回格式不对，请重试。原始返回：{_result[:200]}")
                else:
                    st.error(f"生成失败: {_err or '请确认 Claude Code CLI 已安装'}")

_todos_expanded = st.session_state.get("todos_open", False)
with st.expander(_todo_label, expanded=_todos_expanded):
    st.session_state["todos_open"] = True  # stays open once user opens it
    pending = todos[todos["status"] == "pending"]
    done = todos[todos["status"] == "done"]
    if len(pending) == 0 and len(done) == 0:
        st.caption("—")
    else:
        for _, row in pending.iterrows():
            cols = st.columns([0.05, 0.95])
            if cols[0].button(t("todo_mark_done", lang), key=f"todo_done_{row['id']}"):
                write_todo_status(int(row["id"]), "done")
                st.session_state["todos_open"] = True
                st.rerun()
            cols[1].write(f"☐ {todo_text(row, lang)}")
        for _, row in done.iterrows():
            cols = st.columns([0.05, 0.95])
            if cols[0].button(t("todo_reopen", lang), key=f"todo_open_{row['id']}"):
                write_todo_status(int(row["id"]), "pending")
                st.session_state["todos_open"] = True
                st.rerun()
            cols[1].markdown(f"☑ ~~{todo_text(row, lang)}~~")


# ----------------- Category tabs -----------------

categories = load_categories()
counts = {cat["id"]: int((emails_view["category"] == cat["id"]).sum()) for cat in categories}
total_in_view = len(emails_view)

tab_labels = [f"{t('tab_all', lang)} ({total_in_view})"]
for cat in categories:
    tab_labels.append(f"{cat_name(cat, lang)} ({counts[cat['id']]})")

tabs = st.tabs(tab_labels)


def render_email_card(row, lang: str, tab_key: str):
    cat = get_category(row["category"])
    is_demo = bool(row["is_demo"])
    status_emoji = {"new": "🆕", "drafted": "📝", "completed": "✅"}.get(row["status"], "❔")
    demo_marker = f" `{t('demo_badge', lang)}`" if is_demo else ""
    account_marker = f" 📬 {row['account_id']}" if row.get("account_id") else ""
    sender = row["from_name"] or row["from_addr"]
    title = f"{status_emoji}  **{sender}** — {row['subject']}{account_marker}{demo_marker}"
    eid = int(row["id"])

    exp_key = f"exp_{tab_key}_{eid}"
    if exp_key not in st.session_state:
        st.session_state[exp_key] = False
    with st.expander(title, expanded=st.session_state[exp_key]):
        col_a, col_b = st.columns([3, 1])

        with col_a:
            if row.get("account_id"):
                st.markdown(
                    f"**{t('account', lang)}:** {_account_chip(row['account_id'])}",
                    unsafe_allow_html=True,
                )
            st.markdown(f"**{t('from', lang)}:** {row['from_addr']}")
            st.markdown(f"**{t('received', lang)}:** {row['received_at']}")
            summary = email_summary(row, lang)
            if summary and isinstance(summary, str) and summary.strip() and summary.strip() != "nan":
                st.info(f"📌 {summary}")
            kf_raw = row["key_fields"]
            if kf_raw and isinstance(kf_raw, str):
                try:
                    kf = json.loads(kf_raw)
                    if kf:
                        st.markdown(f"**{t('key_fields', lang)}:**")
                        st.json(kf)
                except json.JSONDecodeError:
                    pass

            atts = load_attachments(eid)
            _att_hdr, _att_btn = st.columns([3, 2])
            _att_hdr.markdown(f"**{t('attachments', lang)}:**")
            if not row.get("is_demo") and _att_btn.button("🔄 刷新附件", key=f"{tab_key}_refetch_att_{eid}", help="从 Outlook 重新拉取附件"):
                try:
                    from core.outlook import list_attachments as _la, download_attachment as _da
                    _conn_r = get_conn()
                    _er = _conn_r.execute("SELECT message_id, account_id FROM emails WHERE id = ?", (eid,)).fetchone()
                    _conn_r.close()
                    if _er and _er["message_id"]:
                        _ol_atts = _la(_er["message_id"], account=_er["account_id"])
                        _attach_dir = Path(__file__).resolve().parent.parent / "data" / "attachments" / _er["message_id"][:30]
                        _conn_w = get_conn()
                        for _a in _ol_atts:
                            if _a.get("@odata.type") != "#microsoft.graph.fileAttachment":
                                continue
                            _sp = _attach_dir / _a["name"]
                            try:
                                _da(_er["message_id"], _a["id"], _sp, account=_er["account_id"])
                            except Exception:
                                pass
                            _rel = str(_sp.relative_to(Path(__file__).resolve().parent.parent))
                            _exists = _conn_w.execute(
                                "SELECT id FROM attachments WHERE email_id=? AND filename=?", (eid, _a["name"])
                            ).fetchone()
                            if not _exists:
                                _conn_w.execute(
                                    "INSERT INTO attachments (email_id, filename, local_path, size_bytes, outlook_attachment_id, is_demo) VALUES (?,?,?,?,?,0)",
                                    (eid, _a["name"], _rel, _a.get("size", 0), _a["id"])
                                )
                        _conn_w.commit()
                        _conn_w.close()
                        st.cache_data.clear()
                        st.session_state[exp_key] = True
                        st.rerun()
                except Exception as _ex:
                    st.error(f"刷新附件失败: {_ex}")
            if len(atts) > 0:
                for _, att in atts.iterrows():
                    fname = att["filename"] or ""
                    downloaded = att.get("downloaded_to")
                    a_col1, a_col2 = st.columns([3, 2])
                    a_col1.caption(f"📎 {fname}")
                    if downloaded and isinstance(downloaded, str) and Path(downloaded).exists():
                        a_col2.caption(f"✅ `{downloaded}`")
                    else:
                        if a_col2.button("⬇ 下载到本地", key=f"{tab_key}_att_{att['id']}"):
                            folder = pick_folder()
                            if folder:
                                dst = Path(folder) / fname
                                try:
                                    src = Path(__file__).resolve().parent.parent / att["local_path"] if att.get("local_path") else None
                                    if src and src.exists():
                                        shutil.copy2(src, dst)
                                    else:
                                        # Re-download from Outlook
                                        from core.outlook import download_attachment as _dl_att
                                        _email_row = get_conn().execute(
                                            "SELECT message_id, account_id FROM emails WHERE id = ?", (eid,)
                                        ).fetchone()
                                        if _email_row and _email_row["message_id"]:
                                            _dl_att(_email_row["message_id"], att["attachment_id"] if att.get("attachment_id") else att["id"], dst, account=_email_row["account_id"])
                                        else:
                                            dst.parent.mkdir(parents=True, exist_ok=True)
                                            raise FileNotFoundError("本地文件不存在且无法从 Outlook 重新下载")
                                    write_attachment_downloaded(int(att["id"]), str(dst))
                                    st.toast(f"已保存到 {dst}", icon="✅")
                                    st.session_state[exp_key] = True
                                    st.rerun()
                                except Exception as ex:
                                    st.error(f"下载失败: {ex}")

            with st.container(border=True):
                body_text = row["body"] or ""
                translated = row.get("body_translated")
                if translated and isinstance(translated, str):
                    t_tab, o_tab = st.tabs(["译文", "原文"])
                    with t_tab:
                        st.text(translated)
                    with o_tab:
                        st.text(body_text)
                else:
                    st.text(body_text)

        with col_b:
            st.markdown(f"**{t('status', lang)}:** `{row['status']}`")
            st.markdown(f"**{t('category', lang)}:** {cat_name(cat, lang)}")
            st.caption(t("confidence", lang))
            st.progress(float(row["category_confidence"] or 0))

            if row["status"] != "completed":
                if st.button(t("mark_done", lang), key=f"{tab_key}_done_{eid}"):
                    write_status(eid, "completed")
                    st.session_state[exp_key] = True
                    st.rerun()
            else:
                if st.button(t("reopen", lang), key=f"{tab_key}_reopen_{eid}"):
                    write_status(eid, "new")
                    st.session_state[exp_key] = True
                    st.rerun()

            if row["status"] == "new":
                if st.button(t("draft_one", lang), key=f"{tab_key}_draft1_{eid}"):
                    with st.spinner("Claude 起草中…"):
                        _subj = row.get("subject", "") or ""
                        _from = row.get("from_addr", "") or ""
                        _body = clean_body(row.get("body", "") or "")
                        email_lang = detect_email_lang(_subj, _body)
                        reply_lang = "中文" if email_lang == "zh" else "English"
                        prompt = (
                            f"[邮件原文开始]\nFrom: {_from}\nSubject: {_subj}\n\n{_body[:2000]}\n[邮件原文结束]\n\n"
                            f"以上邮件的专业回复（{reply_lang}，只写回复正文）："
                        )
                        draft, _derr = call_claude(prompt)
                    st.session_state[exp_key] = True
                    if draft:
                        write_draft(eid, draft)
                        st.rerun()
                    else:
                        email_lang2 = detect_email_lang(_subj, _body)
                        template = cat_template(cat, email_lang2)
                        kf = json.loads(row["key_fields"]) if isinstance(row["key_fields"], str) and row["key_fields"] else {}
                        write_draft(eid, render_draft(template, kf))
                        st.rerun()

            st.divider()
            if st.button("🌐 翻译成中文", key=f"{tab_key}_trans_{eid}", use_container_width=True):
                with st.spinner("翻译中…"):
                    body_text = clean_body(row.get("body", "") or "")
                    try:
                        from deep_translator import GoogleTranslator
                        result = GoogleTranslator(source="auto", target="zh-CN").translate(body_text[:4000])
                    except Exception as _te:
                        result = None
                        st.error(f"翻译失败: {_te}")
                if result:
                    write_translation(eid, result)
                    st.toast("翻译完成", icon="🌐")
                    st.session_state[exp_key] = True
                    st.rerun()

            if st.button("📝 一键总结", key=f"{tab_key}_summ_{eid}", use_container_width=True):
                with st.spinner("总结中…"):
                    body_text = clean_body(row.get("body", "") or "")
                    # Summarise with Claude, then translate to Chinese with Google
                    p_en = f"Write one sentence describing what this email text is about (do not open any files):\n\n{body_text[:2000]}"
                    s_en, _ = call_claude(p_en)
                    s_en = s_en or ""
                    if s_en:
                        try:
                            from deep_translator import GoogleTranslator
                            s_zh = GoogleTranslator(source="auto", target="zh-CN").translate(s_en)
                        except Exception:
                            s_zh = s_en
                    else:
                        s_zh = ""
                if s_zh or s_en:
                    write_summary(eid, s_zh, s_en)
                    st.toast("总结完成", icon="📝")
                    st.session_state[exp_key] = True
                    st.rerun()
                else:
                    st.error("总结失败，请确认 Claude Code 已安装")

        draft_val = row["draft_text"]
        draft_content = draft_val if isinstance(draft_val, str) else ""
        if row["status"] in ("drafted",) or draft_content.strip():
            st.markdown("---")
            st.markdown(f"**{t('draft_label', lang)}:**")
            new_draft = st.text_area(
                " ",
                draft_content,
                key=f"{tab_key}_draft_{eid}",
                height=140,
                label_visibility="collapsed",
            )
            cx, cy, _ = st.columns([1, 1, 4])
            if cx.button(t("save_draft", lang), key=f"{tab_key}_save_{eid}"):
                write_draft(eid, new_draft)
                # Push to Outlook Drafts folder
                try:
                    from core.outlook import create_draft_reply
                    from core.db import get_conn as _gc
                    _conn = _gc()
                    _r = _conn.execute(
                        "SELECT message_id, account_id, outlook_draft_id FROM emails WHERE id = ?", (eid,)
                    ).fetchone()
                    _conn.close()
                    if _r and _r["message_id"] and not _r["outlook_draft_id"]:
                        draft_obj = create_draft_reply(_r["message_id"], new_draft, account=_r["account_id"])
                        _conn2 = _gc()
                        _conn2.execute(
                            "UPDATE emails SET outlook_draft_id = ?, draft_pushed_at = datetime('now') WHERE id = ?",
                            (draft_obj.get("id"), eid),
                        )
                        _conn2.commit()
                        _conn2.close()
                        st.toast("已保存并推送到 Outlook 草稿箱", icon="📬")
                    elif _r and _r["outlook_draft_id"]:
                        st.toast("草稿已存在于 Outlook，仅更新本地", icon="💾")
                    else:
                        st.toast(t("save_draft_done", lang), icon="💾")
                except Exception as _e:
                    st.toast(f"本地已保存，Outlook 推送失败: {_e}", icon="⚠️")
                st.cache_data.clear()
                st.session_state[exp_key] = True
                st.rerun()
            if cy.button(t("discard_draft", lang), key=f"{tab_key}_discard_{eid}"):
                # Delete from Outlook Drafts
                _ol_ok = False
                try:
                    from core.outlook import delete_message, find_and_delete_draft_by_subject
                    from core.db import get_conn as _gc
                    _conn = _gc()
                    _r = _conn.execute(
                        "SELECT outlook_draft_id, account_id, subject FROM emails WHERE id = ?", (eid,)
                    ).fetchone()
                    _conn.close()
                    if _r and _r["outlook_draft_id"]:
                        delete_message(_r["outlook_draft_id"], account=_r["account_id"])
                        _ol_ok = True
                    elif _r and _r["account_id"]:
                        _ol_ok = find_and_delete_draft_by_subject(_r["subject"] or "", account=_r["account_id"])
                    if _ol_ok:
                        st.toast("Outlook 草稿已删除", icon="🗑️")
                    else:
                        st.toast("本地已清除，Outlook 未找到对应草稿（可手动删除）", icon="⚠️")
                except Exception as _e:
                    st.error(f"Outlook 删除失败: {_e}")
                # Clear local DB
                conn = get_conn()
                conn.execute(
                    "UPDATE emails SET draft_text = NULL, outlook_draft_id = NULL, "
                    "draft_pushed_at = NULL, status = 'new' WHERE id = ?",
                    (eid,),
                )
                conn.commit()
                conn.close()
                st.cache_data.clear()
                st.rerun()


def render_category(df, cat: dict | None, lang: str, tab_key: str):
    if cat and cat["id"] != "other" and len(df) > 0:
        st.markdown(f"### {t('batch_actions', lang)}")
        ca, cb, _ = st.columns([2, 1, 4])
        if ca.button(t("batch_draft_all", lang), key=f"{tab_key}_batch_draft"):
            n = 0
            for _, row in df.iterrows():
                if row["status"] == "new":
                    email_lang = detect_email_lang(row.get("subject", ""), row.get("body", "") or "")
                    template = cat_template(cat, email_lang)
                    kf = json.loads(row["key_fields"]) if isinstance(row["key_fields"], str) and row["key_fields"] else {}
                    write_draft(int(row["id"]), render_draft(template, kf))
                    n += 1
            st.success(t("batch_done_msg", lang, n=n))
            st.rerun()
        if cb.button(t("batch_archive_all", lang), key=f"{tab_key}_batch_arch"):
            for _, row in df.iterrows():
                write_status(int(row["id"]), "completed")
            st.rerun()
        st.divider()

    if len(df) == 0:
        st.info(t("no_emails", lang))
        return

    for _, row in df.iterrows():
        render_email_card(row, lang, tab_key)


with tabs[0]:
    render_category(emails_view, None, lang, "all")

for i, cat in enumerate(categories):
    with tabs[i + 1]:
        df = emails_view[emails_view["category"] == cat["id"]]
        render_category(df, cat, lang, f"cat_{cat['id']}")


# ---- Floating AI Chat Panel (pure HTML/CSS/JS — no Streamlit rerun for open/close) ----
if "chat_msgs" not in st.session_state:
    st.session_state["chat_msgs"] = load_chat_history()

# Build messages HTML
import html as _html
_msgs_html = ""
for _m in st.session_state["chat_msgs"][-25:]:
    _txt = _html.escape(str(_m["content"])).replace("\n", "<br>")
    if _m["role"] == "user":
        _msgs_html += f'<div style="text-align:right;margin:6px 0"><span style="background:#6366f1;color:#fff;padding:9px 14px;border-radius:14px 14px 2px 14px;display:inline-block;max-width:82%;font-size:15px;text-align:left;line-height:1.5">{_txt}</span></div>'
    else:
        _msgs_html += f'<div style="text-align:left;margin:6px 0"><span style="background:#f1f5f9;color:#1e293b;padding:9px 14px;border-radius:14px 14px 14px 2px;display:inline-block;max-width:82%;font-size:15px;line-height:1.5">{_txt}</span></div>'

st.markdown(f"""
<style>
/* CSS-only chat panel — no onclick needed (Streamlit strips them) */
#chat-toggle {{ display:none; }}

#chat-fab-label {{
    position:fixed; bottom:24px; right:24px; width:54px; height:54px;
    border-radius:50%; background:linear-gradient(135deg,#6366f1,#8b5cf6);
    color:#fff; font-size:24px; display:flex; align-items:center; justify-content:center;
    cursor:pointer; box-shadow:0 4px 16px rgba(99,102,241,.45);
    z-index:9999; user-select:none; transition:transform .15s;
}}
#chat-fab-label:hover {{ transform:scale(1.1); }}

#chat-panel {{
    display:none; position:fixed; bottom:90px; right:24px; width:460px; height:600px;
    background:#fff; border-radius:18px; box-shadow:0 12px 40px rgba(0,0,0,.18);
    z-index:9998; flex-direction:column; overflow:hidden;
    font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
}}
#chat-resize-handle {{
    position:absolute; top:0; left:0; width:28px; height:28px;
    cursor:nw-resize; display:flex; align-items:center; justify-content:center;
    color:rgba(255,255,255,0.6); font-size:13px; border-radius:18px 0 8px 0;
    user-select:none; z-index:10;
    transition:color 0.2s;
}}
#chat-resize-handle:hover {{ color:rgba(255,255,255,1); }}
/* Show panel when checkbox is checked */
#chat-toggle:checked ~ #chat-panel {{ display:flex; }}

#chat-input {{
    flex:1; padding:10px 14px; border:1px solid #e2e8f0; border-radius:10px;
    font-size:15px; outline:none; font-family:inherit;
    transition: border-color 0.2s;
}}
#chat-input:focus {{ border-color:#6366f1; box-shadow:0 0 0 3px rgba(99,102,241,0.12); }}
#chat-send {{
    padding:10px 18px; background:linear-gradient(135deg,#6366f1,#8b5cf6); color:#fff; border:none;
    border-radius:10px; cursor:pointer; font-size:15px; font-weight:500;
    box-shadow:0 3px 10px rgba(99,102,241,0.3); transition:opacity 0.2s;
}}
#chat-send:hover {{ opacity:0.9; }}
#chat-send:disabled {{ opacity:0.5; cursor:not-allowed; }}
</style>

<!-- Hidden checkbox controls open/close state -->
<input type="checkbox" id="chat-toggle">

<!-- FAB = label that toggles the checkbox -->
<label for="chat-toggle" id="chat-fab-label" title="AI 邮件助手">💬</label>

<!-- Chat panel (sibling of checkbox so CSS ~ selector works) -->
<div id="chat-panel">
  <!-- Top-left resize handle -->
  <div id="chat-resize-handle" title="拖拽调整大小">⤢</div>
  <div style="padding:12px 16px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;font-weight:600;font-size:14px;display:flex;justify-content:space-between;align-items:center;">
    <span>💬 AI 邮件助手</span>
    <!-- Close button = label that unchecks the checkbox -->
    <label for="chat-toggle" style="cursor:pointer;font-size:18px;opacity:.8;line-height:1">✕</label>
  </div>
  <div id="chat-msgs" style="flex:1;overflow-y:auto;padding:12px 14px;background:#fafafa">
    {_msgs_html if _msgs_html else '<div id="chat-empty" style="color:#94a3b8;text-align:center;margin-top:40px;font-size:13px">查找邮件、总结内容、建议回复…</div>'}
  </div>
  <div style="display:flex;gap:8px;padding:10px 12px;border-top:1px solid #e2e8f0;background:#fff">
    <input id="chat-input" type="text" placeholder="查找邮件、总结、建议回复…" autocomplete="off"
      style="flex:1;padding:10px 14px;border:1px solid #e2e8f0;border-radius:10px;font-size:15px;outline:none;font-family:inherit;">
    <button id="chat-send" type="button"
      style="padding:10px 18px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;border:none;border-radius:10px;cursor:pointer;font-size:15px;font-weight:500;">发送</button>
  </div>
</div>
""", unsafe_allow_html=True)

# Inject working JS via same-origin component iframe
# (st.markdown scripts are blocked by React; components.html runs normally)
import streamlit.components.v1 as _cv1
_cv1.html("""
<script>
var _p = window.parent;
var _d = _p.document;

// addMsg in parent DOM
_p._chatAddMsg = function(role, text) {
  var el = _d.getElementById('chat-empty');
  if (el) el.remove();
  var box = _d.getElementById('chat-msgs');
  if (!box) return null;
  var div = _d.createElement('div');
  div.style.cssText = 'margin:6px 0;text-align:' + (role==='user'?'right':'left');
  var span = _d.createElement('span');
  span.style.cssText = 'padding:9px 14px;display:inline-block;max-width:82%;font-size:15px;line-height:1.5;white-space:pre-wrap;' +
    (role==='user'
      ? 'background:#6366f1;color:#fff;border-radius:14px 14px 2px 14px;text-align:left'
      : 'background:#f1f5f9;color:#1e293b;border-radius:14px 14px 14px 2px;');
  span.textContent = text;
  div.appendChild(span);
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  return span;
};

// sendChat in parent context
_p._chatSend = function() {
  var inp = _d.getElementById('chat-input');
  if (!inp) return;
  var msg = inp.value.trim();
  if (!msg) return;
  inp.value = '';
  _p._chatAddMsg('user', msg);
  var loadSpan = _p._chatAddMsg('assistant', '正在思考…');
  var btn = _d.getElementById('chat-send');
  if (btn) btn.disabled = true;
  _p.fetch('http://127.0.0.1:8502/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message: msg})
  }).then(function(r){ return r.json(); })
    .then(function(data){
      if (loadSpan) loadSpan.textContent = data.reply || '(无回复)';
      var box = _d.getElementById('chat-msgs');
      if (box) box.scrollTop = box.scrollHeight;
    })
    .catch(function(e){ if (loadSpan) loadSpan.textContent = '⚠️ ' + e; })
    .finally(function(){ if (btn) btn.disabled = false; });
};

// Resize from top-left handle
if (!_p._chatResizeSet) {
  _p._chatResizeSet = true;
  _d.addEventListener('mousedown', function(e) {
    if (!e.target || e.target.id !== 'chat-resize-handle') return;
    e.preventDefault();
    var panel = _d.getElementById('chat-panel');
    if (!panel) return;
    var startX = e.clientX, startY = e.clientY;
    var startW = panel.offsetWidth, startH = panel.offsetHeight;
    function onMove(ev) {
      var dx = startX - ev.clientX;  // dragging left = wider
      var dy = startY - ev.clientY;  // dragging up = taller
      var newW = Math.max(320, startW + dx);
      var newH = Math.max(400, startH + dy);
      panel.style.width = newW + 'px';
      panel.style.height = newH + 'px';
    }
    function onUp() {
      _d.removeEventListener('mousemove', onMove);
      _d.removeEventListener('mouseup', onUp);
    }
    _d.addEventListener('mousemove', onMove);
    _d.addEventListener('mouseup', onUp);
  });
}

// Attach delegated events once in parent document
if (!_p._chatEventsSet) {
  _p._chatEventsSet = true;
  _d.addEventListener('click', function(e) {
    if (e.target && e.target.id === 'chat-send') _p._chatSend();
  });
  _d.addEventListener('keydown', function(e) {
    if (e.target && e.target.id === 'chat-input' && e.key === 'Enter') _p._chatSend();
  });
}

// Scroll to bottom
var m = _d.getElementById('chat-msgs');
if (m) m.scrollTop = m.scrollHeight;
</script>
""", height=0)
