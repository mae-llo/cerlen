"""Text formatting shared by commands and automatic posts."""

from __future__ import annotations

from datetime import date, datetime

from cerlen.ratings import format_rating


def parse_date(text: str) -> date | None:
    """Accepts 2026-11-14 (ISO) and 11/14/2026 style dates."""
    text = text.strip()
    for pattern in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def fmt_deadline(value: str | None) -> str:
    """'2026-11-14' -> 'Friday 14 November'; no deadline -> 'no set date'."""
    if not value:
        return "no set date"
    return datetime.strptime(value, "%Y-%m-%d").strftime("%A %d %B")


def progress_text(page: int, pages: int | None) -> str:
    if pages:
        return f"{page} of {pages} pages"
    return f"page {page}"


def percent(page: int, pages: int | None) -> int:
    if not pages:
        return 0
    return max(0, min(100, round(page / pages * 100)))


def progress_bar(page: int, pages: int | None, width: int = 10) -> str:
    if not pages:
        return f"page {page}"
    filled = round(percent(page, pages) / 100 * width)
    return f"{'█' * filled}{'░' * (width - filled)} {percent(page, pages)}%"


def stars(units: float) -> str:
    """17 -> '★★★★☆ 4.25'"""
    value = units / 4
    full = int(value)
    return f"{'★' * full}{'☆' * (5 - full)} {format_rating(units)}"
