"""Personal reading statistics, shown on a member's profile."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from cerlen.db import Database
from cerlen.util import iso


@dataclass(frozen=True)
class RatedBook:
    title: str
    units: int


@dataclass(frozen=True)
class UserStats:
    highest: RatedBook | None
    lowest: RatedBook | None
    finished_this_year: int
    finished_this_month: int
    average_units: float | None
    club_finished: int
    total_finished: int

    @property
    def club_share(self) -> float | None:
        """Club books finished as a share of all books finished (0 to 100)."""
        if not self.total_finished:
            return None
        return 100 * self.club_finished / self.total_finished


_RATED = """SELECT b.title AS title, rv.rating_units AS units
            FROM reviews rv
            JOIN readings rd ON rd.id = rv.reading_id
            JOIN books b ON b.id = rd.book_id
            WHERE rd.user_id = ?
            ORDER BY rv.rating_units {order}, rv.created_at ASC LIMIT 1"""


async def user_stats(db: Database, user_id: int, now: datetime) -> UserStats:
    """Did-not-finish books have no rating and are never counted as finished."""
    now = now.astimezone(timezone.utc)
    year_start = iso(now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0))
    month_start = iso(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))

    high = await db.fetchone(_RATED.format(order="DESC"), (user_id,))
    low = await db.fetchone(_RATED.format(order="ASC"), (user_id,))

    counts = await db.fetchone(
        """SELECT
             COUNT(*) AS total,
             COALESCE(SUM(club_read_id IS NOT NULL), 0) AS club,
             COALESCE(SUM(finished_at >= ?), 0) AS this_year,
             COALESCE(SUM(finished_at >= ?), 0) AS this_month
           FROM readings WHERE user_id = ? AND status = 'finished'""",
        (year_start, month_start, user_id),
    )
    average = await db.fetchone(
        """SELECT AVG(rv.rating_units) AS avg_units
           FROM reviews rv JOIN readings rd ON rd.id = rv.reading_id
           WHERE rd.user_id = ?""",
        (user_id,),
    )
    assert counts is not None and average is not None
    return UserStats(
        highest=RatedBook(high["title"], high["units"]) if high else None,
        lowest=RatedBook(low["title"], low["units"]) if low else None,
        finished_this_year=int(counts["this_year"]),
        finished_this_month=int(counts["this_month"]),
        average_units=average["avg_units"],
        club_finished=int(counts["club"]),
        total_finished=int(counts["total"]),
    )
