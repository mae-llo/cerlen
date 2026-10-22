"""All database reads and writes, in one place."""

from __future__ import annotations

import aiosqlite

from cerlen.books.models import BookData
from cerlen.db import Database
from cerlen.ratings import format_rating
from cerlen.util import iso, utcnow

MAX_FAVORITES = 5

# Only these guild_settings columns can be changed through set_setting.
SETTING_COLUMNS = {
    "admin_role_id",
    "announcement_channel_id",
    "discussion_channel_id",
    "reviews_channel_id",
    "tag_book_of_the_month",
    "tag_other_reads",
    "reminder_time",
    "reminder_timezone",
    "reminder_days",
}

# Only these profile columns can be changed through set_profile_field.
PROFILE_FIELDS = {"goodreads", "storygraph", "favorite_genre"}


# --- guild settings -------------------------------------------------------


async def get_settings(db: Database, guild_id: int) -> aiosqlite.Row:
    await db.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
    row = await db.fetchone("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,))
    assert row is not None
    return row


async def set_setting(db: Database, guild_id: int, column: str, value: object) -> None:
    if column not in SETTING_COLUMNS:
        raise ValueError(f"Unknown setting: {column}")
    await get_settings(db, guild_id)
    await db.execute(f"UPDATE guild_settings SET {column} = ? WHERE guild_id = ?", (value, guild_id))


# --- books ----------------------------------------------------------------


async def get_book(db: Database, book_id: int) -> aiosqlite.Row | None:
    return await db.fetchone("SELECT * FROM books WHERE id = ?", (book_id,))


async def get_book_by_isbn(db: Database, isbn13: str) -> aiosqlite.Row | None:
    return await db.fetchone("SELECT * FROM books WHERE isbn13 = ?", (isbn13,))


async def upsert_book(db: Database, book: BookData) -> int:
    """Save a book and return its id. Existing outside ratings are never touched."""
    existing = None
    if book.isbn13:
        existing = await db.fetchone("SELECT id FROM books WHERE isbn13 = ?", (book.isbn13,))
    if existing is None and book.open_library_key:
        existing = await db.fetchone(
            "SELECT id FROM books WHERE open_library_key = ?", (book.open_library_key,)
        )
    now = iso(utcnow())
    if existing is not None:
        await db.execute(
            """UPDATE books SET
                 isbn13 = COALESCE(isbn13, ?), open_library_key = COALESCE(open_library_key, ?),
                 google_id = COALESCE(?, google_id), title = ?, authors = ?,
                 year = COALESCE(?, year), pages = COALESCE(?, pages),
                 subjects = CASE WHEN ? != '' THEN ? ELSE subjects END,
                 cover_url = COALESCE(?, cover_url), blurb = COALESCE(?, blurb), fetched_at = ?
               WHERE id = ?""",
            (
                book.isbn13, book.open_library_key, book.google_id, book.title, book.authors,
                book.year, book.pages, book.subjects, book.subjects, book.cover_url,
                book.blurb, now, existing["id"],
            ),
        )
        return int(existing["id"])
    result = await db.execute(
        """INSERT INTO books (isbn13, open_library_key, google_id, title, authors, year, pages,
                              subjects, cover_url, blurb, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            book.isbn13, book.open_library_key, book.google_id, book.title, book.authors,
            book.year, book.pages, book.subjects, book.cover_url, book.blurb, now,
        ),
    )
    assert result.lastrowid is not None
    return result.lastrowid


async def search_local_books(db: Database, text: str, limit: int = 5) -> list[aiosqlite.Row]:
    pattern = "%" + text.replace("%", "").replace("_", "") + "%"
    return await db.fetchall(
        """SELECT * FROM books WHERE title LIKE ? OR authors LIKE ?
           ORDER BY title COLLATE NOCASE LIMIT ?""",
        (pattern, pattern, limit),
    )


async def set_outside_ratings(
    db: Database, book_id: int, goodreads: float | None, storygraph: float | None
) -> None:
    await db.execute(
        "UPDATE books SET goodreads_rating = ?, storygraph_rating = ? WHERE id = ?",
        (goodreads, storygraph, book_id),
    )


async def book_status(db: Database, guild_id: int, book_id: int, user_id: int) -> list[str]:
    """Plain-text status lines for the book card."""
    lines: list[str] = []

    active = await db.fetchone(
        "SELECT kind FROM club_reads WHERE guild_id = ? AND book_id = ? AND status = 'active'",
        (guild_id, book_id),
    )
    if active:
        lines.append(
            "Current Book of the Month" if active["kind"] == "book_of_the_month" else "Current Other read"
        )

    queued = await db.fetchone(
        "SELECT position FROM queue_items WHERE guild_id = ? AND book_id = ?", (guild_id, book_id)
    )
    if queued:
        lines.append(f"In the server queue (#{queued['position']})")

    finished = await db.fetchone(
        "SELECT COUNT(*) AS n FROM club_reads WHERE guild_id = ? AND book_id = ? AND status = 'finished'",
        (guild_id, book_id),
    )
    if finished and finished["n"]:
        stats = await db.fetchone(
            """SELECT AVG(rv.rating_units) AS avg_units, COUNT(rv.id) AS n
               FROM reviews rv
               JOIN readings rd ON rd.id = rv.reading_id
               JOIN club_reads cr ON cr.id = rd.club_read_id
               WHERE cr.guild_id = ? AND cr.book_id = ? AND cr.status = 'finished'""",
            (guild_id, book_id),
        )
        if stats and stats["n"]:
            lines.append(
                f"Read by the club, average {format_rating(stats['avg_units'])} from {stats['n']} ratings"
            )
        else:
            lines.append("Read by the club, no ratings yet")

    on_tbr = await db.fetchone(
        "SELECT 1 FROM user_tbr WHERE user_id = ? AND book_id = ?", (user_id, book_id)
    )
    if on_tbr:
        lines.append("In your TBR")

    return lines or ["Not tracked"]


# --- personal TBR and server queue ------------------------------------------


async def add_to_user_tbr(db: Database, user_id: int, book_id: int) -> bool:
    """Returns False if the book was already on the member's TBR."""
    row = await db.fetchone(
        "SELECT COALESCE(MAX(position), 0) + 1 AS next FROM user_tbr WHERE user_id = ?", (user_id,)
    )
    result = await db.execute(
        "INSERT OR IGNORE INTO user_tbr (user_id, book_id, position, added_at) VALUES (?, ?, ?, ?)",
        (user_id, book_id, row["next"] if row else 1, iso(utcnow())),
    )
    return result.rowcount > 0


async def add_to_queue(db: Database, guild_id: int, book_id: int, user_id: int) -> tuple[bool, int]:
    """Returns (added, number of books now in the queue)."""
    row = await db.fetchone(
        "SELECT COALESCE(MAX(position), 0) + 1 AS next FROM queue_items WHERE guild_id = ?", (guild_id,)
    )
    result = await db.execute(
        """INSERT OR IGNORE INTO queue_items (guild_id, book_id, position, added_by, added_at)
           VALUES (?, ?, ?, ?, ?)""",
        (guild_id, book_id, row["next"] if row else 1, user_id, iso(utcnow())),
    )
    count = await db.fetchone("SELECT COUNT(*) AS n FROM queue_items WHERE guild_id = ?", (guild_id,))
    return result.rowcount > 0, int(count["n"]) if count else 0


# --- profiles and favorites -----------------------------------------------


async def get_profile(db: Database, user_id: int) -> aiosqlite.Row | None:
    return await db.fetchone("SELECT * FROM profiles WHERE user_id = ?", (user_id,))


async def set_profile_field(db: Database, user_id: int, field: str, value: str | None) -> None:
    if field not in PROFILE_FIELDS:
        raise ValueError(f"Unknown profile field: {field}")
    await db.execute("INSERT OR IGNORE INTO profiles (user_id) VALUES (?)", (user_id,))
    await db.execute(f"UPDATE profiles SET {field} = ? WHERE user_id = ?", (value, user_id))


async def list_favorites(db: Database, user_id: int) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """SELECT f.slot, b.id AS book_id, b.title, b.authors
           FROM favorites f JOIN books b ON b.id = f.book_id
           WHERE f.user_id = ? ORDER BY f.slot""",
        (user_id,),
    )


async def set_favorite(db: Database, user_id: int, book_id: int, position: int | None) -> str:
    """Add a favorite. Returns 'added', 'replaced', 'exists' or 'full'.

    With no position the book takes the next free slot. With a position it takes
    that slot (replacing what is there), but never leaves a gap: a position past
    the end becomes the next free slot.
    """
    current = await list_favorites(db, user_id)
    if any(row["book_id"] == book_id for row in current):
        return "exists"

    count = len(current)
    if position is None:
        if count >= MAX_FAVORITES:
            return "full"
        slot, outcome = count + 1, "added"
    elif position > count:
        slot, outcome = count + 1, "added"
    else:
        slot, outcome = position, "replaced"

    await db.execute(
        """INSERT INTO favorites (user_id, slot, book_id) VALUES (?, ?, ?)
           ON CONFLICT (user_id, slot) DO UPDATE SET book_id = excluded.book_id""",
        (user_id, slot, book_id),
    )
    return outcome


async def remove_favorite(db: Database, user_id: int, book_id: int) -> bool:
    """Remove a favorite and close the gap so slots stay 1..n."""
    result = await db.execute(
        "DELETE FROM favorites WHERE user_id = ? AND book_id = ?", (user_id, book_id)
    )
    if result.rowcount == 0:
        return False
    remaining = await db.fetchall(
        "SELECT slot FROM favorites WHERE user_id = ? ORDER BY slot", (user_id,)
    )
    moves = [
        ("UPDATE favorites SET slot = ? WHERE user_id = ? AND slot = ?", (index, user_id, row["slot"]))
        for index, row in enumerate(remaining, start=1)
        if row["slot"] != index
    ]
    if moves:
        await db.batch(moves)
    return True
