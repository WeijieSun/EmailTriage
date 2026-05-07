"""Email Assistant Skill — search, summarize, draft replies.

This skill reads the email DB and Outlook data.
It NEVER modifies application code — only email records.

Capabilities:
  - search: find emails by keyword / sender / subject
  - summarize: summarize one or multiple emails in Chinese
  - draft: suggest a reply draft for a specific email
"""
from __future__ import annotations
from pathlib import Path
from .db import get_conn


def _clean(text: str, max_len: int = 500) -> str:
    import re
    if not text:
        return ""
    text = text.replace("â€™", "'").replace("â€œ", '"').replace("â€", '"')
    text = text.replace("â€™", " ").replace("ï»¿", " ").replace("â€", " ")
    text = re.sub(r"\?{3,}", " ", text)
    text = re.sub(r"[A-Za-z]:\\(?:[^\s\\]+\\)*([^\s\\\n]+)", r"\1", text)
    text = re.sub(r"[^\x09\x0a\x0d\x20-\x7e一-鿿　-〿＀-￯]", " ", text)
    text = re.sub(r" {3,}", " ", text)
    return text.strip()[:max_len]


def _build_index(emails) -> str:
    lines = []
    for e in emails:
        lines.append("ID:%-3s [%-12s] 状态:%-9s 来自:%-30s 主题:%s" % (
            e["id"], e["category"] or "other", e["status"],
            (e["from_addr"] or "")[:30], e["subject"] or ""
        ))
    return "\n".join(lines)


def _search_emails(keyword: str) -> list:
    kw = f"%{keyword.lower()}%"
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, subject, from_addr, body, summary, category, status "
        "FROM emails WHERE is_demo=0 AND "
        "(LOWER(subject) LIKE ? OR LOWER(from_addr) LIKE ? OR LOWER(body) LIKE ?) "
        "LIMIT 5",
        (kw, kw, kw)
    ).fetchall()
    conn.close()
    return rows


def answer(user_query: str, call_claude_fn) -> str:
    """Answer an email-related query. Returns Chinese response."""
    conn = get_conn()
    all_emails = conn.execute(
        "SELECT id, subject, from_addr, category, status, summary "
        "FROM emails WHERE is_demo=0 ORDER BY received_at DESC LIMIT 50"
    ).fetchall()
    conn.close()

    index = _build_index(all_emails)

    # Search for emails relevant to the query
    matched = _search_emails(user_query)
    match_ctx = ""
    if matched:
        parts = []
        for m in matched:
            body = _clean(m["body"] or "", 500)
            summ = (m["summary"] or "").strip()
            parts.append(
                "ID:%s 主题:%s 来自:%s\n摘要:%s\n正文节选:%s" % (
                    m["id"], m["subject"] or "", m["from_addr"] or "",
                    summ or "(无)", body
                )
            )
        match_ctx = "\n\n相关邮件详情：\n" + "\n---\n".join(parts)

    prompt = (
        "[任务] 你是一个邮件收件箱助手。以下是用户的真实收件箱数据。\n"
        "只根据以下邮件数据回答用户的问题，不要讨论如何构建系统，不要问用户技术问题。\n"
        "用中文简洁回答，直接给出结果。\n\n"
        "[收件箱邮件列表]\n%s\n%s\n"
        "[用户问题] %s\n"
        "[回答]"
    ) % (index, match_ctx, user_query)

    result, err = call_claude_fn(prompt, timeout=120)
    return result or f"⚠️ 无法回答：{err}"
