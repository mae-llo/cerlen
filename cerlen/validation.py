"""Checks for text that members and admins type in."""

from __future__ import annotations

import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_USERNAME = re.compile(r"^[A-Za-z0-9._-]{2,50}$")
_GOODREADS_URL = re.compile(r"^https://(www\.)?goodreads\.com/[A-Za-z0-9_\-./?=%&]{1,150}$")
_GENRE = re.compile(r"^[\w ,&'’/-]{2,40}$")
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class InvalidInput(ValueError):
    pass


def clean_storygraph(value: str) -> str:
    value = value.strip()
    if not _USERNAME.match(value):
        raise InvalidInput("storygraph")
    return value


def clean_goodreads(value: str) -> str:
    """Accept a Goodreads username or a full goodreads.com profile link."""
    value = value.strip()
    if value.lower().startswith("https://"):
        if not _GOODREADS_URL.match(value):
            raise InvalidInput("goodreads")
        return value
    if not _USERNAME.match(value):
        raise InvalidInput("goodreads")
    return value


def clean_genre(value: str) -> str:
    value = " ".join(value.split())
    if not _GENRE.match(value) or "_" in value:
        raise InvalidInput("genre")
    return value


def goodreads_link(stored: str) -> tuple[str, str]:
    """Return (label, url) for a stored Goodreads value."""
    if stored.lower().startswith("https://"):
        return "Goodreads profile", stored
    return stored, f"https://www.goodreads.com/{stored}"


def storygraph_link(stored: str) -> tuple[str, str]:
    return stored, f"https://app.thestorygraph.com/profile/{stored}"


def parse_time(value: str) -> str:
    value = value.strip()
    if not _TIME.match(value):
        raise InvalidInput("time")
    return value


def parse_timezone(value: str) -> str:
    value = value.strip()
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise InvalidInput("timezone") from None
    return value


def parse_days(value: str) -> str:
    """'7, 3, 1, 0' -> '7,3,1,0' (largest first, no repeats, 0 to 60)."""
    try:
        days = {int(part) for part in value.replace(" ", "").split(",") if part != ""}
    except ValueError:
        raise InvalidInput("days") from None
    if not days or any(day < 0 or day > 60 for day in days):
        raise InvalidInput("days")
    return ",".join(str(day) for day in sorted(days, reverse=True))
