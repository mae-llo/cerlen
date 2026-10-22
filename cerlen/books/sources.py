"""Turn Open Library and Google Books responses into BookData.

These are plain functions with no network access so they are easy to test.
"""

from __future__ import annotations

import html
import re

from cerlen.books.isbn import is_valid_isbn13, to_isbn13
from cerlen.books.models import BookData

OPEN_LIBRARY_SEARCH = "https://openlibrary.org/search.json"
OPEN_LIBRARY_FIELDS = "key,title,author_name,first_publish_year,number_of_pages_median,isbn,cover_i,subject"
GOOGLE_VOLUMES = "https://www.googleapis.com/books/v1/volumes"

_TAGS = re.compile(r"<[^>]+>")
_BREAKS = re.compile(r"</?(?:br|p)\s*/?>", re.IGNORECASE)


def clean_blurb(text: str | None) -> str | None:
    if not text:
        return None
    text = html.unescape(_TAGS.sub("", _BREAKS.sub(" ", text)))
    text = " ".join(text.split())
    return text or None


def parse_open_library_doc(doc: dict) -> BookData | None:
    title = (doc.get("title") or "").strip()
    if not title:
        return None

    isbn13 = None
    candidates = doc.get("isbn") or []
    for candidate in candidates:
        if isinstance(candidate, str) and len(candidate) == 13 and is_valid_isbn13(candidate):
            isbn13 = candidate
            break
    if isbn13 is None:
        for candidate in candidates:
            if isinstance(candidate, str):
                isbn13 = to_isbn13(candidate)
                if isbn13:
                    break

    cover_id = doc.get("cover_i")
    cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None
    pages = doc.get("number_of_pages_median")

    return BookData(
        title=title,
        authors=", ".join(doc.get("author_name") or [])[:200],
        isbn13=isbn13,
        year=doc.get("first_publish_year") if isinstance(doc.get("first_publish_year"), int) else None,
        pages=pages if isinstance(pages, int) and pages > 0 else None,
        subjects=", ".join((doc.get("subject") or [])[:5])[:200],
        cover_url=cover_url,
        open_library_key=doc.get("key"),
    )


def parse_google_volume(item: dict) -> BookData | None:
    info = item.get("volumeInfo") or {}
    title = (info.get("title") or "").strip()
    if not title:
        return None
    subtitle = (info.get("subtitle") or "").strip()
    if subtitle:
        title = f"{title}: {subtitle}"

    identifiers = {entry.get("type"): entry.get("identifier") for entry in info.get("industryIdentifiers", [])}
    isbn13 = to_isbn13(identifiers.get("ISBN_13") or "") or to_isbn13(identifiers.get("ISBN_10") or "")

    cover = (info.get("imageLinks") or {}).get("thumbnail")
    if cover:
        cover = cover.replace("http://", "https://").replace("&edge=curl", "")

    year = None
    published = str(info.get("publishedDate") or "")
    if published[:4].isdigit():
        year = int(published[:4])

    pages = info.get("pageCount")
    return BookData(
        title=title,
        authors=", ".join(info.get("authors") or [])[:200],
        isbn13=isbn13,
        year=year,
        pages=pages if isinstance(pages, int) and pages > 0 else None,
        subjects=", ".join((info.get("categories") or [])[:5])[:200],
        cover_url=cover,
        blurb=clean_blurb(info.get("description")),
        google_id=item.get("id"),
    )
