import pytest

from cerlen import repo


async def test_personal_tbr_no_duplicates(db, book_ids):
    assert await repo.add_to_user_tbr(db, 1, book_ids[0]) is True
    assert await repo.add_to_user_tbr(db, 1, book_ids[0]) is False
    assert await repo.add_to_user_tbr(db, 2, book_ids[0]) is True


async def test_queue_counts(db, book_ids):
    assert await repo.add_to_queue(db, 10, book_ids[0], 1) == (True, 1)
    assert await repo.add_to_queue(db, 10, book_ids[1], 1) == (True, 2)
    assert await repo.add_to_queue(db, 10, book_ids[1], 1) == (False, 2)


async def test_book_status(db, book_ids):
    assert await repo.book_status(db, 10, book_ids[0], 1) == ["Not tracked"]
    await repo.add_to_queue(db, 10, book_ids[0], 1)
    await repo.add_to_user_tbr(db, 1, book_ids[0])
    lines = await repo.book_status(db, 10, book_ids[0], 1)
    assert any("queue" in line for line in lines) and "In your TBR" in lines


async def test_settings_defaults_and_whitelist(db):
    s = await repo.get_settings(db, 10)
    assert s["reminder_time"] == "09:00" and s["reminder_timezone"] == "America/New_York"
    await repo.set_setting(db, 10, "reminder_days", "3,1")
    assert (await repo.get_settings(db, 10))["reminder_days"] == "3,1"
    with pytest.raises(ValueError):
        await repo.set_setting(db, 10, "guild_id", 5)


async def test_outside_ratings(db, book_ids):
    await repo.set_outside_ratings(db, book_ids[0], 4.1, None)
    row = await repo.get_book(db, book_ids[0])
    assert row["goodreads_rating"] == 4.1 and row["storygraph_rating"] is None
