from datetime import datetime, timezone

from cerlen.stats import user_stats


async def _finish(db, user, book, units, when, club=None):
    cur = await db.execute(
        "INSERT INTO readings (user_id, book_id, status, started_at, finished_at) VALUES (?, ?, 'finished', ?, ?)",
        (user, book, when, when),
    )
    if units:
        await db.execute(
            "INSERT INTO reviews (reading_id, rating_units, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (cur.lastrowid, units, when, when),
        )


async def test_user_stats_ignores_dnf_and_counts_periods(db, book_ids):
    now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
    await _finish(db, 1, book_ids[0], 20, "2026-10-02T00:00:00+00:00")
    await _finish(db, 1, book_ids[1], 8, "2026-03-02T00:00:00+00:00")
    await db.execute(
        "INSERT INTO readings (user_id, book_id, status, started_at) VALUES (1, ?, 'dnf', '2026-01-01T00:00:00+00:00')",
        (book_ids[2],),
    )
    stats = await user_stats(db, 1, now)
    assert stats.total_finished == 2
    assert stats.finished_this_year == 2 and stats.finished_this_month == 1
    assert stats.highest.units == 20 and stats.lowest.units == 8
    assert stats.average_units == 14


async def test_empty_stats(db):
    stats = await user_stats(db, 99, datetime(2026, 10, 21, tzinfo=timezone.utc))
    assert stats.total_finished == 0 and stats.highest is None and stats.average_units is None
