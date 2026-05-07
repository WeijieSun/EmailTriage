"""Keyword-based classifier for the demo path.

In production the skill calls Claude to do classification + key-field extraction;
this fallback exists so the dashboard works end-to-end with seed data, without an LLM.
"""
from __future__ import annotations

import re
import yaml
from pathlib import Path
from functools import lru_cache

CATEGORIES_FILE = Path(__file__).resolve().parent / "categories.yaml"


@lru_cache(maxsize=1)
def load_categories():
    with open(CATEGORIES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)["categories"]


def reload_categories():
    load_categories.cache_clear()
    return load_categories()


def _kw_match(kw: str, text: str) -> bool:
    """ASCII keywords match on word boundaries (so "PO" doesn't match "repo");
    Chinese keywords use plain substring (Chinese has no spaces)."""
    kw_lower = kw.lower()
    if re.fullmatch(r"[\x00-\x7f]+", kw):
        return re.search(rf"\b{re.escape(kw_lower)}\b", text) is not None
    return kw_lower in text


def classify_keyword(subject: str, body: str) -> tuple[str, float]:
    text = f"{subject}\n{body}".lower()
    best_id = "other"
    best_score = 0
    for cat in load_categories():
        if cat["id"] == "other":
            continue
        score = sum(1 for kw in cat["keywords"] if _kw_match(kw, text))
        if score > best_score:
            best_score = score
            best_id = cat["id"]
    confidence = min(0.6 + 0.1 * best_score, 0.99) if best_score > 0 else 0.3
    return best_id, confidence


def get_category(cat_id: str) -> dict:
    for cat in load_categories():
        if cat["id"] == cat_id:
            return cat
    return next(c for c in load_categories() if c["id"] == "other")


def render_draft(template: str, key_fields: dict) -> str:
    out = template
    for k, v in (key_fields or {}).items():
        out = out.replace(f"{{{{{k}}}}}", str(v))
    return out
