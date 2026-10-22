"""ISBN checks and conversion."""

from __future__ import annotations

import re


def clean(text: str) -> str:
    return re.sub(r"[\s-]", "", text).upper()


def is_valid_isbn10(value: str) -> bool:
    if not re.fullmatch(r"\d{9}[\dX]", value):
        return False
    total = sum((10 - i) * (10 if ch == "X" else int(ch)) for i, ch in enumerate(value))
    return total % 11 == 0


def is_valid_isbn13(value: str) -> bool:
    if not re.fullmatch(r"\d{13}", value):
        return False
    total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(value))
    return total % 10 == 0


def to_isbn13(value: str) -> str | None:
    """Return a valid ISBN-13 for an ISBN-10 or ISBN-13, or None."""
    value = clean(value)
    if is_valid_isbn13(value):
        return value
    if is_valid_isbn10(value):
        core = "978" + value[:9]
        total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(core))
        return core + str((10 - total % 10) % 10)
    return None
