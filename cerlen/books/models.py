"""The book record shared by the lookup clients, the database and the cards."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace


@dataclass
class BookData:
    title: str
    authors: str = ""
    isbn13: str | None = None
    year: int | None = None
    pages: int | None = None
    subjects: str = ""
    cover_url: str | None = None
    blurb: str | None = None
    open_library_key: str | None = None
    google_id: str | None = None


def merge(primary: BookData, secondary: BookData | None) -> BookData:
    """Fill any empty field of `primary` from `secondary`."""
    if secondary is None:
        return primary
    updates = {}
    for field in fields(BookData):
        if not getattr(primary, field.name) and getattr(secondary, field.name):
            updates[field.name] = getattr(secondary, field.name)
    return replace(primary, **updates)
