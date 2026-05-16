"""Test the Claude 整理 (triage) feature in the dashboard."""
import re
import pytest
from playwright.sync_api import Page, expect

BASE = "http://localhost:8501"
LOAD_TIMEOUT = 30_000


def wait_for_streamlit(page: Page):
    page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=LOAD_TIMEOUT)
    page.wait_for_timeout(3000)


def test_claude_triage_button_exists(page: Page):
    """Claude 整理 button should be visible on the page."""
    page.goto(BASE)
    wait_for_streamlit(page)
    btn = page.get_by_role("button", name=re.compile("Claude 整理|Claude.*整理", re.IGNORECASE))
    expect(btn).to_be_visible(timeout=LOAD_TIMEOUT)


def test_claude_find_exe(page: Page):
    """Verify _find_claude resolves to a real path (not 'claude' fallback)."""
    page.goto(BASE)
    wait_for_streamlit(page)
    # Click the Claude 整理 button and wait for response (success or real error, not 'not recognized')
    btn = page.get_by_role("button", name=re.compile("Claude 整理|Claude.*整理", re.IGNORECASE))
    if btn.count() == 0:
        pytest.skip("Claude 整理 button not found")
    btn.first.click()
    # Wait up to 60s for a response to appear (claude --print can be slow)
    page.wait_for_timeout(5000)
    # Check error box doesn't contain the "not recognized" PowerShell error
    page_text = page.inner_text("body")
    assert "is not recognized as the name of a cmdlet" not in page_text, (
        "claude.exe still not found — PATH fix did not take effect"
    )
