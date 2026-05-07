"""Translation strings for the dashboard. Add a key here once, use it everywhere."""

LANGS = {"zh": "中文", "en": "English"}

STRINGS = {
    "app_title": {"zh": "📧 邮件分类助手", "en": "📧 Email Triage Dashboard"},
    "language": {"zh": "语言", "en": "Language"},
    "metric_total": {"zh": "总邮件", "en": "Total"},
    "metric_new": {"zh": "待处理", "en": "New"},
    "metric_drafted": {"zh": "已起草", "en": "Drafted"},
    "metric_completed": {"zh": "已完成", "en": "Completed"},
    "tab_all": {"zh": "全部", "en": "All"},
    "filter_status": {"zh": "状态筛选", "en": "Filter by status"},
    "filter_all": {"zh": "全部", "en": "All"},
    "status_new": {"zh": "待处理", "en": "New"},
    "status_drafted": {"zh": "已起草", "en": "Drafted"},
    "status_completed": {"zh": "已完成", "en": "Completed"},
    "batch_actions": {"zh": "批量操作", "en": "Batch actions"},
    "batch_draft_all": {"zh": "📝 批量起草此分类回复", "en": "📝 Draft replies for this category"},
    "batch_archive_all": {"zh": "✓ 全部归档", "en": "✓ Archive all"},
    "batch_done_msg": {"zh": "已为 {n} 封邮件起草回复", "en": "Drafted replies for {n} emails"},
    "no_emails": {"zh": "此分类暂无邮件", "en": "No emails in this category"},
    "from": {"zh": "发件人", "en": "From"},
    "received": {"zh": "接收时间", "en": "Received"},
    "summary": {"zh": "摘要", "en": "Summary"},
    "key_fields": {"zh": "关键字段", "en": "Key fields"},
    "body": {"zh": "正文", "en": "Body"},
    "status": {"zh": "状态", "en": "Status"},
    "category": {"zh": "分类", "en": "Category"},
    "confidence": {"zh": "分类置信度", "en": "Confidence"},
    "mark_done": {"zh": "✅ 标记完成", "en": "✅ Mark done"},
    "reopen": {"zh": "↩️ 重新打开", "en": "↩️ Reopen"},
    "draft_label": {"zh": "回复草稿", "en": "Draft reply"},
    "save_draft": {"zh": "💾 保存草稿", "en": "💾 Save draft"},
    "save_draft_done": {"zh": "已保存", "en": "Saved"},
    "draft_one": {"zh": "📝 起草回复", "en": "📝 Draft reply"},
    "discard_draft": {"zh": "🗑️ 丢弃草稿", "en": "🗑️ Discard draft"},
    "attachments": {"zh": "📎 附件", "en": "📎 Attachments"},
    "todos_section": {"zh": "📋 待办事项", "en": "📋 To-Dos"},
    "todo_pending": {"zh": "待办", "en": "Pending"},
    "todo_done": {"zh": "已完成", "en": "Done"},
    "todo_mark_done": {"zh": "✓", "en": "✓"},
    "todo_reopen": {"zh": "↩", "en": "↩"},
    "footer_db": {"zh": "数据库", "en": "Database"},
    "footer_refresh": {"zh": "🔄 刷新", "en": "🔄 Refresh"},
    "auto_refresh": {"zh": "自动刷新", "en": "Auto-refresh"},
    "wipe_demo": {"zh": "🧹 清除 Demo 数据", "en": "🧹 Wipe demo data"},
    "wipe_demo_confirm": {"zh": "确认清除全部 Demo 数据？此操作不可恢复。", "en": "Confirm wiping all demo data? This cannot be undone."},
    "wipe_demo_done": {"zh": "Demo 数据已清除", "en": "Demo data wiped"},
    "demo_badge": {"zh": "DEMO", "en": "DEMO"},
    "settings": {"zh": "⚙️ 设置", "en": "⚙️ Settings"},
    "filters": {"zh": "🔍 筛选", "en": "🔍 Filters"},
    "show_demo_only": {"zh": "仅显示 Demo 数据", "en": "Show demo data only"},
    "show_real_only": {"zh": "仅显示真实数据", "en": "Show real data only"},
    "data_source": {"zh": "数据来源", "en": "Data source"},
    "data_all": {"zh": "全部", "en": "All"},
    "data_demo": {"zh": "Demo", "en": "Demo"},
    "data_real": {"zh": "真实", "en": "Real"},
    "last_processed": {"zh": "上次处理", "en": "Last processed"},
    "never": {"zh": "从未", "en": "never"},
    "unprocessed_alert": {"zh": "🆕 有 {n} 封新邮件待处理", "en": "🆕 {n} new email(s) waiting"},
    "unprocessed_none": {"zh": "✅ 所有邮件已处理", "en": "✅ All caught up"},
    "account": {"zh": "账户", "en": "Account"},
    "all_accounts": {"zh": "全部账户", "en": "All accounts"},
    "account_filter": {"zh": "邮箱账户筛选", "en": "Filter by account"},
    "no_accounts": {"zh": "未登录任何 Outlook 账户。在终端运行 'python -m core.outlook login' 添加。", "en": "No Outlook accounts signed in. Run 'python -m core.outlook login' to add one."},
    "daily_actions": {"zh": "🚀 一键日常", "en": "🚀 Daily one-click"},
    "daily_run": {"zh": "拉取 → 处理 → 推送草稿", "en": "Fetch → process → push drafts"},
    "daily_running": {"zh": "正在执行...", "en": "Running..."},
    "daily_done": {"zh": "完成：拉了 {f} 封 / 处理 {p} 封 / 推送 {d} 封草稿", "en": "Done: fetched {f} / processed {p} / pushed {d} drafts"},
    "daily_step_fetch": {"zh": "1/3 拉取新邮件", "en": "1/3 Fetching new emails"},
    "daily_step_process": {"zh": "2/3 处理未处理的邮件", "en": "2/3 Processing new emails"},
    "daily_step_push": {"zh": "3/3 推送草稿到 Outlook", "en": "3/3 Pushing drafts to Outlook"},
    "daily_demo_mode": {"zh": "（Demo 模式：模拟新邮件，跳过推送）", "en": "(Demo mode: simulate inflow, skip push)"},
    "daily_pull_source": {"zh": "拉取来源", "en": "Fetch source"},
    "source_outlook": {"zh": "真实 Outlook", "en": "Real Outlook"},
    "source_simulate": {"zh": "Demo 模拟", "en": "Demo simulate"},
}


def t(key: str, lang: str = "zh", **kwargs) -> str:
    s = STRINGS.get(key, {}).get(lang) or STRINGS.get(key, {}).get("zh") or key
    if kwargs:
        try:
            return s.format(**kwargs)
        except KeyError:
            return s
    return s


def cat_name(category: dict, lang: str) -> str:
    if lang == "en":
        return category.get("name_en") or category.get("name") or category["id"]
    return category.get("name") or category["id"]


def cat_template(category: dict, lang: str) -> str:
    if lang == "en":
        return category.get("draft_template_en") or category.get("draft_template_zh") or ""
    return category.get("draft_template_zh") or category.get("draft_template_en") or ""


def _str(v) -> str:
    return v if isinstance(v, str) and v.strip() else ""


def email_summary(row, lang: str) -> str:
    if lang == "en":
        return _str(row["summary_en"]) or _str(row["summary"])
    return _str(row["summary"]) or _str(row["summary_en"])


def todo_text(row, lang: str) -> str:
    if lang == "en":
        return _str(row["description_en"]) or _str(row["description"])
    return _str(row["description"]) or _str(row["description_en"])
