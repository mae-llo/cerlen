"""Small helpers shared across the bot."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    """Store every timestamp as UTC text so string comparison matches time order."""
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def trim(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def humanize_duration(delta: timedelta) -> str:
    """A short, approximate span such as '3 days' or '1 year, 4 months'."""
    days = max(delta.days, 0)
    if days < 1:
        return "less than a day"
    years, rest = divmod(days, 365)
    months = rest // 30
    if years:
        text = _plural(years, "year")
        if months:
            text += ", " + _plural(months, "month")
        return text
    if months:
        return _plural(months, "month")
    return _plural(days, "day")
