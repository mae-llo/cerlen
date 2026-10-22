"""Looks books up from Open Library and Google Books and saves them to the database."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import aiohttp

from cerlen import repo
from cerlen.books.isbn import clean, to_isbn13
from cerlen.books.models import BookData, merge
from cerlen.books.sources import (
    GOOGLE_VOLUMES,
    OPEN_LIBRARY_FIELDS,
    OPEN_LIBRARY_SEARCH,
    parse_google_volume,
    parse_open_library_doc,
)
from cerlen.db import Database
from cerlen.util import trim

log = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=8)
# Discord gives autocomplete 3 seconds in total, so suggestions use a short timeout.
AUTOCOMPLETE_TIMEOUT = aiohttp.ClientTimeout(total=2)
CACHE_SECONDS = 600
CACHE_LIMIT = 200


@dataclass(frozen=True)
class Suggestion:
    label: str
    value: str


class BookService:
    def __init__(self, session: aiohttp.ClientSession, db: Database):
        self.session = session
        self.db = db
        self._cache: dict[str, tuple[float, list[BookData]]] = {}

    # --- network -----------------------------------------------------------

    async def _get_json(
        self, url: str, params: dict, timeout: aiohttp.ClientTimeout = TIMEOUT
    ) -> dict | None:
        try:
            async with self.session.get(url, params=params, timeout=timeout) as response:
                if response.status != 200:
                    log.warning("%s answered %s", url, response.status)
                    return None
                return await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
            log.warning("Request to %s failed: %s", url, error)
            return None

    async def _open_library_search(
        self, query: str, limit: int, timeout: aiohttp.ClientTimeout = TIMEOUT
    ) -> list[BookData]:
        key = f"ol:{limit}:{query.lower()}"
        cached = self._cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        data = await self._get_json(
            OPEN_LIBRARY_SEARCH,
            {"q": query, "limit": limit, "fields": OPEN_LIBRARY_FIELDS},
            timeout,
        )
        books = [b for doc in (data or {}).get("docs", []) if (b := parse_open_library_doc(doc))]
        if data is not None:
            if len(self._cache) >= CACHE_LIMIT:
                self._cache.clear()
            self._cache[key] = (time.monotonic() + CACHE_SECONDS, books)
        return books

    async def _google_search(self, query: str) -> BookData | None:
        data = await self._get_json(GOOGLE_VOLUMES, {"q": query, "maxResults": 1, "printType": "books"})
        items = (data or {}).get("items") or []
        return parse_google_volume(items[0]) if items else None

    # --- public ------------------------------------------------------------

    async def suggest(self, query: str, limit: int = 10) -> list[Suggestion]:
        """Autocomplete choices: books already saved first, then Open Library."""
        suggestions: list[Suggestion] = []
        seen: set[str] = set()

        for row in await repo.search_local_books(self.db, query, 5):
            suggestions.append(Suggestion(trim(f"{row['title']} — {row['authors']}", 100), f"db:{row['id']}"))
            if row["isbn13"]:
                seen.add(row["isbn13"])

        isbn = to_isbn13(clean(query))
        if isbn:
            if isbn not in seen:
                suggestions.append(Suggestion(f"ISBN {isbn}", f"isbn:{isbn}"))
            return suggestions[:limit]

        for book in await self._open_library_search(query, 8, AUTOCOMPLETE_TIMEOUT):
            if book.isbn13 and book.isbn13 in seen:
                continue
            year = f" ({book.year})" if book.year else ""
            label = trim(f"{book.title} — {book.authors}{year}", 100)
            value = f"isbn:{book.isbn13}" if book.isbn13 else f"q:{book.title[:90]}"
            suggestions.append(Suggestion(label, value))
            if book.isbn13:
                seen.add(book.isbn13)
        return suggestions[:limit]

    async def fetch_by_isbn(self, isbn13: str) -> int | None:
        existing = await repo.get_book_by_isbn(self.db, isbn13)
        if existing:
            return int(existing["id"])

        open_library, google = await asyncio.gather(
            self._open_library_search(f"isbn:{isbn13}", 1),
            self._google_search(f"isbn:{isbn13}"),
        )
        primary = open_library[0] if open_library else None
        book = merge(primary, google) if primary else google
        if book is None:
            return None
        if not book.isbn13:
            book.isbn13 = isbn13
        return await repo.upsert_book(self.db, book)

    async def resolve(self, value: str) -> int | None:
        """Turn an autocomplete value or typed text into a saved book's id."""
        value = value.strip()
        if not value:
            return None
        if value.startswith("db:") and value[3:].isdigit():
            row = await repo.get_book(self.db, int(value[3:]))
            return int(row["id"]) if row else None
        if value.startswith("isbn:"):
            isbn = to_isbn13(value[5:])
            return await self.fetch_by_isbn(isbn) if isbn else None
        if value.startswith("q:"):
            value = value[2:]

        isbn = to_isbn13(clean(value))
        if isbn:
            return await self.fetch_by_isbn(isbn)

        results = await self._open_library_search(value, 1)
        if results:
            top = results[0]
            if top.isbn13:
                return await self.fetch_by_isbn(top.isbn13)
            return await repo.upsert_book(self.db, merge(top, await self._google_search(value)))

        google = await self._google_search(value)
        return await repo.upsert_book(self.db, google) if google else None
