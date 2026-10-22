from cerlen import repo


async def test_profile_fields(db):
    assert await repo.get_profile(db, 1) is None
    await repo.set_profile_field(db, 1, "goodreads", "reader")
    await repo.set_profile_field(db, 1, "favorite_genre", "Fantasy")
    row = await repo.get_profile(db, 1)
    assert row["goodreads"] == "reader" and row["favorite_genre"] == "Fantasy"
    await repo.set_profile_field(db, 1, "goodreads", None)
    assert (await repo.get_profile(db, 1))["goodreads"] is None


async def test_unknown_profile_field_rejected(db):
    import pytest

    with pytest.raises(ValueError):
        await repo.set_profile_field(db, 1, "user_id; DROP TABLE profiles", "x")


async def test_favorites_fill_replace_and_close_gaps(db, book_ids):
    b = book_ids
    for book in b[:5]:
        assert await repo.set_favorite(db, 1, book, None) == "added"
    assert await repo.set_favorite(db, 1, b[5], None) == "full"
    assert await repo.set_favorite(db, 1, b[0], None) == "exists"

    assert await repo.set_favorite(db, 1, b[5], 2) == "replaced"
    titles = [r["title"] for r in await repo.list_favorites(db, 1)]
    assert titles[1] == "Book 6" and len(titles) == 5

    assert await repo.remove_favorite(db, 1, b[2]) is True
    rows = await repo.list_favorites(db, 1)
    assert [r["slot"] for r in rows] == [1, 2, 3, 4]
    assert await repo.remove_favorite(db, 1, b[2]) is False


async def test_position_past_end_takes_next_slot(db, book_ids):
    assert await repo.set_favorite(db, 1, book_ids[0], 5) == "added"
    assert [r["slot"] for r in await repo.list_favorites(db, 1)] == [1]


async def test_favorites_are_per_member(db, book_ids):
    await repo.set_favorite(db, 1, book_ids[0], None)
    assert await repo.list_favorites(db, 2) == []
