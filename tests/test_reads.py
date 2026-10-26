from datetime import datetime, timedelta, timezone

from cerlen import repo, repo_reads as rr
from cerlen.format import fmt_deadline, parse_date, progress_bar, progress_text, stars


async def _club_read(db, book_id, kind="book_of_the_month", deadline="2026-11-14"):
    return await rr.create_club_read(db, 1, book_id, kind, deadline)


async def test_join_leave_and_participants(db, book_ids):
    read = await _club_read(db, book_ids[0])
    reading, created = await rr.start_reading(db, 5, book_ids[0], read)
    assert created and reading["club_read_id"] == read
    assert [p["user_id"] for p in await rr.participants(db, read)] == [5]
    assert await rr.leave_read(db, 5, read) is True
    assert await rr.participants(db, read) == []
    assert await rr.get_reading(db, 5, book_ids[0]) is not None  # progress stays on the shelf
    assert await rr.leave_read(db, 5, read) is False


async def test_start_reading_removes_from_tbr_and_resumes(db, book_ids):
    await repo.add_to_user_tbr(db, 5, book_ids[0])
    reading, _ = await rr.start_reading(db, 5, book_ids[0])
    assert await rr.tbr_list(db, 5) == []
    await rr.set_reading_status(db, reading["id"], "paused")
    again, created = await rr.start_reading(db, 5, book_ids[0])
    assert not created and again["status"] == "reading"


async def test_one_botm_and_active_lookup(db, book_ids):
    read = await _club_read(db, book_ids[0])
    assert (await rr.active_botm(db, 1))["id"] == read
    assert (await rr.active_read_for_book(db, 1, book_ids[0]))["id"] == read
    await rr.close_read(db, read, "cancelled")
    assert await rr.active_botm(db, 1) is None


async def test_dnf_removes_review_and_is_excluded_from_stats(db, book_ids):
    read = await _club_read(db, book_ids[0])
    reading, _ = await rr.start_reading(db, 5, book_ids[0], read)
    await rr.mark_finished(db, reading["id"], None, 100)
    await rr.save_review(db, reading["id"], 16, "fine", False)
    await rr.mark_dnf(db, reading["id"], 40)
    assert await rr.get_review(db, 5, book_ids[0]) is None
    await rr.close_read(db, read, "finished")
    stats = await rr.server_stats(db, 1)
    assert stats["unique_books"] == 0 and stats["average_units"] is None


async def test_server_stats_average_is_mean_of_book_averages(db, book_ids):
    for index, units in ((0, (20, 16)), (1, (8,))):
        read = await _club_read(db, book_ids[index], deadline=None)
        for user, value in zip((5, 6), units):
            reading, _ = await rr.start_reading(db, user, book_ids[index], read)
            await rr.mark_finished(db, reading["id"], None, None)
            await rr.save_review(db, reading["id"], value, None, False)
        await rr.close_read(db, read, "finished")
    stats = await rr.server_stats(db, 1)
    assert stats["club_books"] == 2 and stats["unique_books"] == 2
    assert stats["average_units"] == (18 + 8) / 2
    assert stats["top"][0]["avg_units"] == 18 and stats["lowest"]["avg_units"] == 8


async def test_review_upsert_and_book_stats_spread(db, book_ids):
    reading, _ = await rr.start_reading(db, 5, book_ids[0])
    await rr.mark_finished(db, reading["id"], None, None)
    await rr.save_review(db, reading["id"], 17, "a", True)
    await rr.save_review(db, reading["id"], 20, "b", False)
    stats = await rr.book_stats(db, book_ids[0])
    assert len(stats["reviews"]) == 1 and stats["average_units"] == 20 and stats["spread"] == {5: 1}


async def test_queue_move_remove_renumber(db, book_ids):
    for book in book_ids[:4]:
        await repo.add_to_queue(db, 1, book, 5)
    await rr.queue_move(db, 1, book_ids[3], 1)
    assert [q["book_id"] for q in await rr.queue_list(db, 1)] == [book_ids[3], *book_ids[:3]]
    await rr.queue_remove(db, 1, book_ids[0])
    assert [q["position"] for q in await rr.queue_list(db, 1)] == [1, 2, 3]
    assert await rr.queue_move(db, 1, 999, 1) is False


async def test_tbr_move_clamps(db, book_ids):
    for book in book_ids[:3]:
        await repo.add_to_user_tbr(db, 5, book)
    await rr.tbr_move(db, 5, book_ids[0], 99)
    assert [t["book_id"] for t in await rr.tbr_list(db, 5)] == [book_ids[1], book_ids[2], book_ids[0]]


async def test_poll_votes_change_and_close(db, book_ids):
    closes = datetime.now(timezone.utc) - timedelta(minutes=1)
    poll = await rr.create_poll(db, 1, 9, closes, book_ids[:2])
    assert await rr.vote(db, poll, 5, book_ids[0]) and await rr.vote(db, poll, 5, book_ids[1])
    assert await rr.vote(db, poll, 6, 999) is False
    options = {o["book_id"]: o["votes"] for o in await rr.poll_options(db, poll)}
    assert options == {book_ids[0]: 0, book_ids[1]: 1}
    assert [p["id"] for p in await rr.due_polls(db)] == [poll]
    await rr.close_poll(db, poll, book_ids[1])
    assert await rr.open_poll(db, 1) is None
    assert await rr.vote(db, poll, 7, book_ids[0]) is False


async def test_logs_in_book_order_and_owner_only_delete(db, book_ids):
    a, _ = await rr.start_reading(db, 5, book_ids[0])
    b, _ = await rr.start_reading(db, 6, book_ids[0])
    await rr.add_log(db, a["id"], 50, "late", False)
    await rr.add_log(db, b["id"], 10, "early", True)
    notes = await rr.list_logs(db, book_ids[0])
    assert [n["text"] for n in notes] == ["early", "late"]
    assert len(await rr.list_logs(db, book_ids[0], 5)) == 1
    assert await rr.delete_log(db, notes[0]["id"], 5) is False  # not theirs
    assert await rr.delete_log(db, notes[0]["id"], 6) is True


async def test_reminder_log_and_seen(db, book_ids):
    read = await _club_read(db, book_ids[0])
    await rr.mark_reminders(db, read, [7, 3])
    await rr.mark_reminders(db, read, [3, 1])
    assert await rr.reminders_sent(db, read) == {7, 3, 1}
    await rr.clear_reminders(db, read)
    assert await rr.reminders_sent(db, read) == set()
    assert await rr.mark_seen(db, 5) is True and await rr.mark_seen(db, 5) is False


async def test_export_and_delete_user(db, book_ids):
    reading, _ = await rr.start_reading(db, 5, book_ids[0])
    await rr.add_log(db, reading["id"], 1, "hi", False)
    await repo.set_profile_field(db, 5, "favorite_genre", "Fantasy")
    data = await rr.export_user(db, 5)
    assert data["log_notes"][0]["text"] == "hi" and data["profile"][0]["favorite_genre"] == "Fantasy"
    await rr.delete_user(db, 5)
    data = await rr.export_user(db, 5)
    assert not data["readings"] and not data["log_notes"] and not data["profile"]


def test_formatting():
    assert parse_date("2026-11-14").isoformat() == "2026-11-14"
    assert parse_date("11/14/2026").isoformat() == "2026-11-14"
    assert parse_date("nope") is None
    assert fmt_deadline("2026-11-14") == "Saturday 14 November"
    assert fmt_deadline(None) == "no set date"
    assert progress_text(120, 310) == "120 of 310 pages" and progress_text(5, None) == "page 5"
    assert progress_bar(155, 310).endswith("50%")
    assert stars(17).endswith("4.25") and stars(20).startswith("★★★★★")
