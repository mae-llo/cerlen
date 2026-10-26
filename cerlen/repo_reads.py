"""Database access for club reads, personal readings, reviews, logs, queue, polls and stats."""

from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite

from cerlen.db import Database
from cerlen.util import iso, utcnow

READ_SELECT = """SELECT cr.*, b.title AS title, b.authors AS authors, b.pages AS pages,
                        b.cover_url AS cover_url, b.isbn13 AS isbn13
                 FROM club_reads cr JOIN books b ON b.id = cr.book_id"""


# --- first-use welcome ------------------------------------------------------


async def mark_seen(db: Database, user_id: int) -> bool:
    """True the first time a member is seen."""
    result = await db.execute(
        "INSERT OR IGNORE INTO seen_users (user_id, first_seen) VALUES (?, ?)", (user_id, iso(utcnow()))
    )
    return result.rowcount > 0


# --- club reads ---------------------------------------------------------------


async def create_club_read(
    db: Database, guild_id: int, book_id: int, kind: str, deadline: str | None
) -> int:
    result = await db.execute(
        """INSERT INTO club_reads (guild_id, book_id, kind, started_at, deadline)
           VALUES (?, ?, ?, ?, ?)""",
        (guild_id, book_id, kind, iso(utcnow()), deadline),
    )
    assert result.lastrowid is not None
    return result.lastrowid


async def get_club_read(db: Database, read_id: int) -> aiosqlite.Row | None:
    return await db.fetchone(READ_SELECT + " WHERE cr.id = ?", (read_id,))


async def active_reads(db: Database, guild_id: int) -> list[aiosqlite.Row]:
    return await db.fetchall(
        READ_SELECT + " WHERE cr.guild_id = ? AND cr.status = 'active' ORDER BY cr.kind DESC, cr.started_at",
        (guild_id,),
    )


async def active_read_for_book(db: Database, guild_id: int, book_id: int) -> aiosqlite.Row | None:
    return await db.fetchone(
        READ_SELECT + " WHERE cr.guild_id = ? AND cr.book_id = ? AND cr.status = 'active'",
        (guild_id, book_id),
    )


async def active_botm(db: Database, guild_id: int) -> aiosqlite.Row | None:
    return await db.fetchone(
        READ_SELECT + " WHERE cr.guild_id = ? AND cr.kind = 'book_of_the_month' AND cr.status = 'active'",
        (guild_id,),
    )


async def set_read_posts(
    db: Database, read_id: int, discussion_post_id: int | None, announcement_message_id: int | None
) -> None:
    await db.execute(
        "UPDATE club_reads SET discussion_post_id = ?, announcement_message_id = ? WHERE id = ?",
        (discussion_post_id, announcement_message_id, read_id),
    )


async def set_deadline(db: Database, read_id: int, deadline: str | None) -> None:
    await db.execute("UPDATE club_reads SET deadline = ? WHERE id = ?", (deadline, read_id))


async def set_reminder_options(
    db: Database, read_id: int, enabled: bool | None = None, days: str | None = None
) -> None:
    if enabled is not None:
        await db.execute("UPDATE club_reads SET reminders_enabled = ? WHERE id = ?", (int(enabled), read_id))
    if days is not None:
        await db.execute("UPDATE club_reads SET reminder_days = ? WHERE id = ?", (days, read_id))


async def close_read(db: Database, read_id: int, status: str) -> None:
    assert status in ("finished", "cancelled")
    await db.execute(
        "UPDATE club_reads SET status = ?, finished_at = ? WHERE id = ?", (status, iso(utcnow()), read_id)
    )


async def read_history(db: Database, guild_id: int, year: int | None) -> list[aiosqlite.Row]:
    sql = (
        """SELECT cr.*, b.title AS title, b.authors AS authors,
                  (SELECT AVG(rv.rating_units) FROM reviews rv JOIN readings rd ON rd.id = rv.reading_id
                   WHERE rd.book_id = cr.book_id) AS avg_units
           FROM club_reads cr JOIN books b ON b.id = cr.book_id
           WHERE cr.guild_id = ? AND cr.status = 'finished'"""
    )
    params: list = [guild_id]
    if year:
        sql += " AND substr(cr.finished_at, 1, 4) = ?"
        params.append(str(year))
    return await db.fetchall(sql + " ORDER BY cr.finished_at DESC", params)


async def finished_read_for_book(db: Database, guild_id: int, book_id: int) -> aiosqlite.Row | None:
    return await db.fetchone(
        READ_SELECT + " WHERE cr.guild_id = ? AND cr.book_id = ? AND cr.status = 'finished' ORDER BY cr.id DESC",
        (guild_id, book_id),
    )


# --- readings ---------------------------------------------------------------------


async def get_reading(db: Database, user_id: int, book_id: int) -> aiosqlite.Row | None:
    return await db.fetchone("SELECT * FROM readings WHERE user_id = ? AND book_id = ?", (user_id, book_id))


async def start_reading(
    db: Database, user_id: int, book_id: int, club_read_id: int | None = None
) -> tuple[aiosqlite.Row, bool]:
    """Returns (reading, created). An existing entry is reopened and linked to the read if given."""
    existing = await get_reading(db, user_id, book_id)
    if existing is None:
        await db.execute(
            "INSERT INTO readings (user_id, book_id, club_read_id, started_at) VALUES (?, ?, ?, ?)",
            (user_id, book_id, club_read_id, iso(utcnow())),
        )
        created = True
    else:
        created = False
        if club_read_id is not None and existing["club_read_id"] != club_read_id:
            await db.execute("UPDATE readings SET club_read_id = ? WHERE id = ?", (club_read_id, existing["id"]))
        if existing["status"] in ("paused",):
            await db.execute("UPDATE readings SET status = 'reading' WHERE id = ?", (existing["id"],))
    await db.execute("DELETE FROM user_tbr WHERE user_id = ? AND book_id = ?", (user_id, book_id))
    reading = await get_reading(db, user_id, book_id)
    assert reading is not None
    return reading, created


async def leave_read(db: Database, user_id: int, read_id: int) -> bool:
    result = await db.execute(
        "UPDATE readings SET club_read_id = NULL WHERE user_id = ? AND club_read_id = ?", (user_id, read_id)
    )
    return result.rowcount > 0


async def participants(db: Database, read_id: int) -> list[aiosqlite.Row]:
    return await db.fetchall(
        "SELECT * FROM readings WHERE club_read_id = ? ORDER BY started_at", (read_id,)
    )


async def set_progress(db: Database, reading_id: int, page: int) -> None:
    await db.execute(
        "UPDATE readings SET current_page = ?, status = CASE WHEN status = 'paused' THEN 'reading' ELSE status END WHERE id = ?",
        (page, reading_id),
    )


async def mark_finished(db: Database, reading_id: int, finished_at: datetime | None, pages: int | None) -> None:
    when = iso(finished_at or utcnow())
    await db.execute(
        """UPDATE readings SET status = 'finished', finished_at = ?,
           current_page = CASE WHEN ? IS NOT NULL THEN ? ELSE current_page END WHERE id = ?""",
        (when, pages, pages, reading_id),
    )


async def mark_dnf(db: Database, reading_id: int, page: int | None) -> None:
    await db.execute("DELETE FROM reviews WHERE reading_id = ?", (reading_id,))
    await db.execute(
        "UPDATE readings SET status = 'dnf', finished_at = NULL, current_page = COALESCE(?, current_page) WHERE id = ?",
        (page, reading_id),
    )


async def set_reading_status(db: Database, reading_id: int, status: str) -> None:
    assert status in ("reading", "paused")
    await db.execute("UPDATE readings SET status = ? WHERE id = ?", (status, reading_id))


async def delete_reading(db: Database, reading_id: int) -> None:
    await db.execute("DELETE FROM readings WHERE id = ?", (reading_id,))


async def user_readings(db: Database, user_id: int, limit: int = 15) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """SELECT rd.*, b.title AS title, b.authors AS authors, b.pages AS pages
           FROM readings rd JOIN books b ON b.id = rd.book_id
           WHERE rd.user_id = ?
           ORDER BY CASE rd.status WHEN 'reading' THEN 0 WHEN 'paused' THEN 1 ELSE 2 END,
                    COALESCE(rd.finished_at, rd.started_at) DESC
           LIMIT ?""",
        (user_id, limit),
    )


async def reading_choices(db: Database, user_id: int, statuses: tuple[str, ...], text: str) -> list[aiosqlite.Row]:
    marks = ",".join("?" * len(statuses))
    return await db.fetchall(
        f"""SELECT b.id AS book_id, b.title AS title, rd.status AS status
            FROM readings rd JOIN books b ON b.id = rd.book_id
            WHERE rd.user_id = ? AND rd.status IN ({marks}) AND b.title LIKE ?
            ORDER BY rd.started_at DESC LIMIT 25""",
        (user_id, *statuses, f"%{text}%"),
    )


# --- personal TBR ---------------------------------------------------------------------


async def tbr_list(db: Database, user_id: int) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """SELECT t.position, b.id AS book_id, b.title, b.authors, b.pages
           FROM user_tbr t JOIN books b ON b.id = t.book_id
           WHERE t.user_id = ? ORDER BY t.position""",
        (user_id,),
    )


async def _renumber(db: Database, table: str, where: str, params: tuple, key: str) -> None:
    rows = await db.fetchall(f"SELECT {key} AS k FROM {table} WHERE {where} ORDER BY position, {key}", params)
    # Two passes so the unique constraint is never hit mid-way.
    statements = []
    for index, row in enumerate(rows, start=1):
        statements.append((f"UPDATE {table} SET position = ? WHERE {where} AND {key} = ?", (-index, *params, row["k"])))
    for index, row in enumerate(rows, start=1):
        statements.append((f"UPDATE {table} SET position = ? WHERE {where} AND {key} = ?", (index, *params, row["k"])))
    if statements:
        await db.batch(statements)


async def tbr_remove(db: Database, user_id: int, book_id: int) -> bool:
    result = await db.execute("DELETE FROM user_tbr WHERE user_id = ? AND book_id = ?", (user_id, book_id))
    if result.rowcount:
        await _renumber(db, "user_tbr", "user_id = ?", (user_id,), "book_id")
    return result.rowcount > 0


async def tbr_move(db: Database, user_id: int, book_id: int, position: int) -> bool:
    rows = await tbr_list(db, user_id)
    ids = [r["book_id"] for r in rows]
    if book_id not in ids:
        return False
    ids.remove(book_id)
    ids.insert(max(0, min(position - 1, len(ids))), book_id)
    await _set_order(db, "user_tbr", "user_id = ?", (user_id,), "book_id", ids)
    return True


async def _set_order(db: Database, table: str, where: str, params: tuple, key: str, ids: list[int]) -> None:
    statements = [
        (f"UPDATE {table} SET position = ? WHERE {where} AND {key} = ?", (-index, *params, value))
        for index, value in enumerate(ids, start=1)
    ] + [
        (f"UPDATE {table} SET position = ? WHERE {where} AND {key} = ?", (index, *params, value))
        for index, value in enumerate(ids, start=1)
    ]
    await db.batch(statements)


# --- server queue -------------------------------------------------------------------------


async def queue_list(db: Database, guild_id: int) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """SELECT q.position, q.added_by, b.id AS book_id, b.title, b.authors, b.pages
           FROM queue_items q JOIN books b ON b.id = q.book_id
           WHERE q.guild_id = ? ORDER BY q.position""",
        (guild_id,),
    )


async def queue_remove(db: Database, guild_id: int, book_id: int) -> bool:
    result = await db.execute("DELETE FROM queue_items WHERE guild_id = ? AND book_id = ?", (guild_id, book_id))
    if result.rowcount:
        await _renumber(db, "queue_items", "guild_id = ?", (guild_id,), "book_id")
    return result.rowcount > 0


async def queue_move(db: Database, guild_id: int, book_id: int, position: int) -> bool:
    ids = [r["book_id"] for r in await queue_list(db, guild_id)]
    if book_id not in ids:
        return False
    ids.remove(book_id)
    ids.insert(max(0, min(position - 1, len(ids))), book_id)
    await _set_order(db, "queue_items", "guild_id = ?", (guild_id,), "book_id", ids)
    return True


# --- polls -------------------------------------------------------------------------------------


async def create_poll(db: Database, guild_id: int, channel_id: int, closes_at: datetime, book_ids: list[int]) -> int:
    result = await db.execute(
        "INSERT INTO polls (guild_id, channel_id, closes_at) VALUES (?, ?, ?)",
        (guild_id, channel_id, iso(closes_at)),
    )
    poll_id = result.lastrowid
    assert poll_id is not None
    await db.batch([("INSERT INTO poll_options (poll_id, book_id) VALUES (?, ?)", (poll_id, b)) for b in book_ids])
    return poll_id


async def open_poll(db: Database, guild_id: int) -> aiosqlite.Row | None:
    return await db.fetchone("SELECT * FROM polls WHERE guild_id = ? AND status = 'open'", (guild_id,))


async def due_polls(db: Database) -> list[aiosqlite.Row]:
    return await db.fetchall(
        "SELECT * FROM polls WHERE status = 'open' AND closes_at <= ?", (iso(utcnow()),)
    )


async def set_poll_message(db: Database, poll_id: int, message_id: int) -> None:
    await db.execute("UPDATE polls SET message_id = ? WHERE id = ?", (message_id, poll_id))


async def poll_options(db: Database, poll_id: int) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """SELECT b.id AS book_id, b.title, b.authors,
                  (SELECT COUNT(*) FROM poll_votes v WHERE v.poll_id = o.poll_id AND v.book_id = o.book_id) AS votes
           FROM poll_options o JOIN books b ON b.id = o.book_id WHERE o.poll_id = ? ORDER BY b.title""",
        (poll_id,),
    )


async def vote(db: Database, poll_id: int, user_id: int, book_id: int) -> bool:
    """False if the poll is closed or the book is not an option."""
    poll = await db.fetchone("SELECT status FROM polls WHERE id = ?", (poll_id,))
    option = await db.fetchone("SELECT 1 FROM poll_options WHERE poll_id = ? AND book_id = ?", (poll_id, book_id))
    if not poll or poll["status"] != "open" or not option:
        return False
    await db.execute(
        """INSERT INTO poll_votes (poll_id, user_id, book_id) VALUES (?, ?, ?)
           ON CONFLICT (poll_id, user_id) DO UPDATE SET book_id = excluded.book_id""",
        (poll_id, user_id, book_id),
    )
    return True


async def close_poll(db: Database, poll_id: int, winner_book_id: int | None) -> None:
    await db.execute(
        "UPDATE polls SET status = 'closed', winner_book_id = ? WHERE id = ?", (winner_book_id, poll_id)
    )


# --- reviews -------------------------------------------------------------------------------------


async def get_review(db: Database, user_id: int, book_id: int) -> aiosqlite.Row | None:
    return await db.fetchone(
        """SELECT rv.*, rd.user_id AS user_id, rd.book_id AS book_id
           FROM reviews rv JOIN readings rd ON rd.id = rv.reading_id
           WHERE rd.user_id = ? AND rd.book_id = ?""",
        (user_id, book_id),
    )


async def save_review(
    db: Database, reading_id: int, units: int, comment: str | None, spoiler: bool
) -> None:
    now = iso(utcnow())
    await db.execute(
        """INSERT INTO reviews (reading_id, rating_units, comment, spoiler, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT (reading_id) DO UPDATE SET rating_units = excluded.rating_units,
             comment = excluded.comment, spoiler = excluded.spoiler, updated_at = excluded.updated_at""",
        (reading_id, units, comment, int(spoiler), now, now),
    )


async def set_review_message(db: Database, review_id: int, message_id: int | None) -> None:
    await db.execute("UPDATE reviews SET message_id = ? WHERE id = ?", (message_id, review_id))


async def delete_review(db: Database, review_id: int) -> None:
    await db.execute("DELETE FROM reviews WHERE id = ?", (review_id,))


async def unreviewed_finished(db: Database, user_id: int, text: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """SELECT b.id AS book_id, b.title AS title
           FROM readings rd JOIN books b ON b.id = rd.book_id
           LEFT JOIN reviews rv ON rv.reading_id = rd.id
           WHERE rd.user_id = ? AND rd.status = 'finished' AND rv.id IS NULL AND b.title LIKE ?
           ORDER BY rd.finished_at DESC LIMIT 25""",
        (user_id, f"%{text}%"),
    )


async def reviewed_books(db: Database, user_id: int, text: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """SELECT b.id AS book_id, b.title AS title
           FROM reviews rv JOIN readings rd ON rd.id = rv.reading_id JOIN books b ON b.id = rd.book_id
           WHERE rd.user_id = ? AND b.title LIKE ? ORDER BY rv.updated_at DESC LIMIT 25""",
        (user_id, f"%{text}%"),
    )


# --- log notes -----------------------------------------------------------------------------------


async def add_log(db: Database, reading_id: int, page: int, text: str, spoiler: bool) -> int:
    result = await db.execute(
        "INSERT INTO log_entries (reading_id, page, text, spoiler, created_at) VALUES (?, ?, ?, ?, ?)",
        (reading_id, page, text, int(spoiler), iso(utcnow())),
    )
    assert result.lastrowid is not None
    return result.lastrowid


async def list_logs(db: Database, book_id: int, user_id: int | None = None) -> list[aiosqlite.Row]:
    """Notes in book order: by page, then by when they were written."""
    sql = """SELECT le.*, rd.user_id AS user_id, b.title AS title
             FROM log_entries le JOIN readings rd ON rd.id = le.reading_id JOIN books b ON b.id = rd.book_id
             WHERE rd.book_id = ?"""
    params: list = [book_id]
    if user_id:
        sql += " AND rd.user_id = ?"
        params.append(user_id)
    return await db.fetchall(sql + " ORDER BY le.page, le.created_at, le.id", params)


async def my_logs(db: Database, user_id: int, text: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """SELECT le.id, le.page, le.text, b.title
           FROM log_entries le JOIN readings rd ON rd.id = le.reading_id JOIN books b ON b.id = rd.book_id
           WHERE rd.user_id = ? AND (le.text LIKE ? OR b.title LIKE ?)
           ORDER BY le.created_at DESC LIMIT 25""",
        (user_id, f"%{text}%", f"%{text}%"),
    )


async def delete_log(db: Database, entry_id: int, user_id: int) -> bool:
    result = await db.execute(
        """DELETE FROM log_entries WHERE id = ? AND reading_id IN
           (SELECT id FROM readings WHERE user_id = ?)""",
        (entry_id, user_id),
    )
    return result.rowcount > 0


async def books_with_logs(db: Database, user_id: int | None, text: str) -> list[aiosqlite.Row]:
    return await db.fetchall(
        """SELECT DISTINCT b.id AS book_id, b.title AS title
           FROM log_entries le JOIN readings rd ON rd.id = le.reading_id JOIN books b ON b.id = rd.book_id
           WHERE b.title LIKE ? ORDER BY b.title LIMIT 25""",
        (f"%{text}%",),
    )


# --- reminders ---------------------------------------------------------------------------------------


async def reminders_sent(db: Database, read_id: int) -> set[int]:
    rows = await db.fetchall("SELECT days_before FROM reminder_log WHERE club_read_id = ?", (read_id,))
    return {int(r["days_before"]) for r in rows}


async def mark_reminders(db: Database, read_id: int, days: list[int]) -> None:
    now = iso(utcnow())
    await db.batch(
        [("INSERT OR IGNORE INTO reminder_log (club_read_id, days_before, sent_at) VALUES (?, ?, ?)", (read_id, d, now)) for d in days]
    )


async def clear_reminders(db: Database, read_id: int) -> None:
    await db.execute("DELETE FROM reminder_log WHERE club_read_id = ?", (read_id,))


# --- statistics -----------------------------------------------------------------------------------------

# Average per club book: reviews of any member's finished reading of that book.
_CLUB_BOOK_AVERAGES = """
    SELECT b.id AS book_id, b.title AS title, b.authors AS authors,
           AVG(rv.rating_units) AS avg_units, COUNT(rv.id) AS n
    FROM books b
    JOIN readings rd ON rd.book_id = b.id
    JOIN reviews rv ON rv.reading_id = rd.id
    WHERE b.id IN (SELECT book_id FROM club_reads WHERE guild_id = ? AND status = 'finished')
    GROUP BY b.id
"""


async def server_stats(db: Database, guild_id: int) -> dict:
    club_total = await db.fetchone(
        "SELECT COUNT(*) AS n FROM club_reads WHERE guild_id = ? AND status = 'finished'", (guild_id,)
    )
    unique_books = await db.fetchone(
        "SELECT COUNT(DISTINCT book_id) AS n FROM readings WHERE status = 'finished'"
    )
    pages = await db.fetchone(
        """SELECT COALESCE(SUM(b.pages), 0) AS n FROM readings rd JOIN books b ON b.id = rd.book_id
           WHERE rd.status = 'finished'"""
    )
    averages = await db.fetchall(_CLUB_BOOK_AVERAGES, (guild_id,))
    overall = sum(r["avg_units"] for r in averages) / len(averages) if averages else None
    ranked = sorted(averages, key=lambda r: (-r["avg_units"], r["title"].lower()))
    readers = await db.fetchall(
        """SELECT user_id, COUNT(*) AS n FROM readings WHERE status = 'finished'
           GROUP BY user_id ORDER BY n DESC, user_id LIMIT 3"""
    )
    return {
        "club_books": int(club_total["n"]),
        "unique_books": int(unique_books["n"]),
        "pages": int(pages["n"]),
        "average_units": overall,
        "top": ranked[:3],
        "lowest": ranked[-1] if ranked else None,
        "readers": readers,
    }


async def book_stats(db: Database, book_id: int) -> dict:
    rows = await db.fetchall(
        """SELECT rd.user_id AS user_id, rd.finished_at AS finished_at, rv.rating_units AS units,
                  rv.comment AS comment, rv.spoiler AS spoiler
           FROM reviews rv JOIN readings rd ON rd.id = rv.reading_id
           WHERE rd.book_id = ? ORDER BY rv.rating_units DESC, rd.finished_at""",
        (book_id,),
    )
    spread: dict[int, int] = {}
    for row in rows:
        star = min(5, int(row["units"] / 4))
        spread[star] = spread.get(star, 0) + 1
    average = sum(r["units"] for r in rows) / len(rows) if rows else None
    finished = await db.fetchone(
        "SELECT COUNT(*) AS n FROM readings WHERE book_id = ? AND status = 'finished'", (book_id,)
    )
    return {"reviews": rows, "average_units": average, "spread": spread, "finished": int(finished["n"])}


# --- your data ----------------------------------------------------------------------------------------------


async def export_user(db: Database, user_id: int) -> dict:
    async def rows(sql: str) -> list[dict]:
        return [dict(r) for r in await db.fetchall(sql, (user_id,))]

    return {
        "exported_at": iso(utcnow()),
        "profile": await rows("SELECT * FROM profiles WHERE user_id = ?"),
        "favorites": await rows(
            "SELECT f.slot, b.title, b.authors FROM favorites f JOIN books b ON b.id = f.book_id WHERE f.user_id = ?"
        ),
        "tbr": await rows(
            "SELECT t.position, b.title, b.authors FROM user_tbr t JOIN books b ON b.id = t.book_id WHERE t.user_id = ?"
        ),
        "readings": await rows(
            """SELECT b.title, b.authors, rd.status, rd.current_page, rd.started_at, rd.finished_at
               FROM readings rd JOIN books b ON b.id = rd.book_id WHERE rd.user_id = ?"""
        ),
        "reviews": await rows(
            """SELECT b.title, rv.rating_units, rv.comment, rv.spoiler, rv.created_at
               FROM reviews rv JOIN readings rd ON rd.id = rv.reading_id JOIN books b ON b.id = rd.book_id
               WHERE rd.user_id = ?"""
        ),
        "log_notes": await rows(
            """SELECT b.title, le.page, le.text, le.spoiler, le.created_at
               FROM log_entries le JOIN readings rd ON rd.id = le.reading_id JOIN books b ON b.id = rd.book_id
               WHERE rd.user_id = ?"""
        ),
    }


async def user_review_messages(db: Database, user_id: int) -> list[int]:
    rows = await db.fetchall(
        """SELECT rv.message_id AS m FROM reviews rv JOIN readings rd ON rd.id = rv.reading_id
           WHERE rd.user_id = ? AND rv.message_id IS NOT NULL""",
        (user_id,),
    )
    return [int(r["m"]) for r in rows]


async def delete_user(db: Database, user_id: int) -> None:
    await db.batch(
        [
            ("DELETE FROM readings WHERE user_id = ?", (user_id,)),  # cascades to reviews and notes
            ("DELETE FROM user_tbr WHERE user_id = ?", (user_id,)),
            ("DELETE FROM favorites WHERE user_id = ?", (user_id,)),
            ("DELETE FROM profiles WHERE user_id = ?", (user_id,)),
            ("DELETE FROM poll_votes WHERE user_id = ?", (user_id,)),
        ]
    )
