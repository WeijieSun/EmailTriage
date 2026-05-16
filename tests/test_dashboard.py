"""Basic smoke tests for the email-triage Streamlit dashboard."""
import re
import pytest
from playwright.sync_api import Page, expect

BASE = "http://localhost:8501"
LOAD_TIMEOUT = 30_000  # ms — Streamlit can be slow on first render


def wait_for_streamlit(page: Page):
    """Wait until Streamlit finishes its initial render cycle."""
    page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=LOAD_TIMEOUT)
    # Wait for the spinner to disappear (running indicator)
    page.wait_for_function(
        "() => !document.querySelector('[data-testid=\"stStatusWidget\"]') || "
        "document.querySelector('[data-testid=\"stStatusWidget\"]').style.display === 'none'",
        timeout=LOAD_TIMEOUT,
    )


# ── Test 1: Page loads and shows title ───────────────────────────────────────

def test_page_title(page: Page):
    page.goto(BASE)
    wait_for_streamlit(page)
    expect(page).to_have_title(re.compile("Email Triage", re.IGNORECASE))


# ── Test 2: Metric cards are visible ─────────────────────────────────────────

def test_metric_cards_visible(page: Page):
    page.goto(BASE)
    wait_for_streamlit(page)
    metrics = page.locator("[data-testid='stMetric']")
    expect(metrics.first).to_be_visible(timeout=LOAD_TIMEOUT)
    count = metrics.count()
    assert count >= 3, f"Expected ≥3 metric cards, got {count}"


# ── Test 3: Category tabs render ─────────────────────────────────────────────

def test_category_tabs(page: Page):
    page.goto(BASE)
    wait_for_streamlit(page)
    tabs = page.locator("[role='tab']")
    expect(tabs.first).to_be_visible(timeout=LOAD_TIMEOUT)
    tab_count = tabs.count()
    assert tab_count >= 2, f"Expected ≥2 tabs (All + categories), got {tab_count}"


# ── Test 4: Sidebar is visible with language selector ────────────────────────

def test_sidebar_visible(page: Page):
    page.goto(BASE)
    wait_for_streamlit(page)
    sidebar = page.locator("[data-testid='stSidebar']")
    expect(sidebar).to_be_visible(timeout=LOAD_TIMEOUT)
    # Language radio buttons should be present
    radios = sidebar.locator("[data-testid='stRadio']")
    expect(radios.first).to_be_visible(timeout=LOAD_TIMEOUT)


# ── Test 5: Language switch zh→en works ──────────────────────────────────────

def test_language_switch(page: Page):
    page.goto(BASE)
    wait_for_streamlit(page)
    sidebar = page.locator("[data-testid='stSidebar']")
    # Click the English radio option (second option in the language radio)
    en_option = sidebar.locator("label").filter(has_text=re.compile(r"English|EN|en", re.IGNORECASE)).first
    if en_option.count() > 0:
        en_option.click()
        page.wait_for_timeout(2000)
    # Should still be functional after switch
    expect(page.locator("[data-testid='stAppViewContainer']")).to_be_visible()


# ── Test 6: Email cards render (if any emails in DB) ─────────────────────────

def test_email_cards_or_empty_state(page: Page):
    page.goto(BASE)
    wait_for_streamlit(page)
    page.wait_for_timeout(3000)
    expanders = page.locator("[data-testid='stExpander']")
    info_boxes = page.locator("[data-testid='stAlert']")
    # Either emails exist or an empty-state info box is shown
    has_emails = expanders.count() > 0
    has_empty = info_boxes.count() > 0
    assert has_emails or has_empty, "Expected email cards or empty-state message"


# ── Test 7: Clicking an email card expands it ────────────────────────────────

def test_expand_email_card(page: Page):
    page.goto(BASE)
    wait_for_streamlit(page)
    page.wait_for_timeout(3000)
    expanders = page.locator("[data-testid='stExpander']")
    if expanders.count() == 0:
        pytest.skip("No email cards to expand (empty DB)")
    first = expanders.first
    # Click the summary to toggle open
    first.locator("summary").click()
    page.wait_for_timeout(1500)
    # The expander content should now be visible
    content = first.locator("[data-testid='stExpanderDetails']")
    expect(content).to_be_visible(timeout=8000)


# ── Test 8: No JavaScript console errors on load ────────────────────────────

def test_no_critical_js_errors(page: Page):
    errors: list[str] = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.goto(BASE)
    wait_for_streamlit(page)
    page.wait_for_timeout(2000)
    # Filter out known benign Streamlit/browser noise
    critical = [e for e in errors if not any(x in e for x in [
        "favicon", "ResizeObserver", "Non-Error exception", "Loading chunk", "Jinja2"
    ])]
    assert critical == [], f"Console errors: {critical[:5]}"
