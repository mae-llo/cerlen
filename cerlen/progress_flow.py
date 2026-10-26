"""Updating progress, finishing and dropping books. Club reads post in their discussion; others reply in place."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

import discord

from cerlen import discussion, repo, repo_reads
from cerlen.format import percent, progress_bar, progress_text
from cerlen.review_flow import review_view

NO_PINGS = discord.AllowedMentions.none()


async def _send(interaction: discord.Interaction, *args, **kwargs):
    """Reply once, whether or not the command already deferred."""
    if kwargs.get("view", ...) is None:
        kwargs.pop("view")
    if interaction.response.is_done():
        return await interaction.followup.send(*args, **kwargs)
    return await interaction.response.send_message(*args, **kwargs)


async def _respond(interaction: discord.Interaction, reading, line: str, detail: str | None = None, view=None):
    """Club reads: line goes to the read's post, the member gets a private note.
    Anything else: the line is posted publicly where the command was run."""
    bot = interaction.client
    read = await repo_reads.get_club_read(bot.db, reading["club_read_id"]) if reading["club_read_id"] else None
    posted = None
    if read is not None:
        posted = await discussion.post(bot, read, line + (f"\n{detail}" if detail else ""), allowed_mentions=NO_PINGS)
    if posted is not None:
        text = bot.voice.say("posted_in_discussion", link=posted.jump_url)
        if detail:
            text = f"{detail}\n{text}"
        await _send(interaction, text, view=view, ephemeral=True)
    elif interaction.response.is_done():
        # The command deferred privately (slow lookup): post publicly, thank privately.
        kwargs = {"view": view} if view is not None else {}
        await interaction.channel.send(
            line + (f"\n{detail}" if detail else ""), allowed_mentions=NO_PINGS, **kwargs
        )
        await interaction.followup.send(bot.voice.say("noted"), ephemeral=True)
    else:
        await _send(
            interaction, line + (f"\n{detail}" if detail else ""), view=view, allowed_mentions=NO_PINGS
        )


async def update_progress(
    interaction: discord.Interaction, book_id: int, page: int | None, percent_value: int | None
) -> None:
    bot, voice = interaction.client, interaction.client.voice
    reading = await repo_reads.get_reading(bot.db, interaction.user.id, book_id)
    book = await repo.get_book(bot.db, book_id)
    if reading is None or book is None:
        await _send(interaction, voice.say("not_reading"), ephemeral=True)
        return
    if reading["status"] in ("finished", "dnf"):
        await _send(interaction, voice.say("reading_closed", title=book["title"]), ephemeral=True)
        return
    if (page is None) == (percent_value is None):
        await _send(interaction, voice.say("need_page_or_percent"), ephemeral=True)
        return

    pages = book["pages"]
    if percent_value is not None:
        if not pages:
            await _send(interaction, voice.say("need_pages_for_percent"), ephemeral=True)
            return
        page = round(percent_value / 100 * pages)
    assert page is not None
    if page < 0 or (pages and page > pages):
        await _send(interaction, voice.say("page_too_high", pages=pages or 0), ephemeral=True)
        return

    before = reading["current_page"]
    await repo_reads.set_progress(bot.db, reading["id"], page)

    mention = interaction.user.mention
    line = voice.say("progress_saved", user=mention, title=book["title"], progress=progress_text(page, pages))
    if pages and before * 2 < pages <= page * 2 and page < pages:
        line += "\n" + voice.say("halfway", user=mention, title=book["title"])
    view = None
    if pages and page >= pages:
        view = discord.ui.View(timeout=600)
        from cerlen.views import FinishButton

        view.add_item(FinishButton(book_id))
    await _respond(interaction, reading, line, progress_bar(page, pages), view)


def _finished_datetime(when: date | None) -> datetime | None:
    if when is None:
        return None
    return datetime.combine(when, time(12, 0), tzinfo=timezone.utc)


async def mark_finished(interaction: discord.Interaction, book_id: int, when: date | None = None) -> None:
    bot, voice = interaction.client, interaction.client.voice
    reading = await repo_reads.get_reading(bot.db, interaction.user.id, book_id)
    book = await repo.get_book(bot.db, book_id)
    if book is None:
        await _send(interaction, voice.say("book_not_found"), ephemeral=True)
        return
    if reading is None:
        # Books finished earlier: create the entry so it can be reviewed.
        reading, _ = await repo_reads.start_reading(bot.db, interaction.user.id, book_id)
    if when and when > date.today():
        await _send(interaction, voice.say("future_date"), ephemeral=True)
        return
    await repo_reads.mark_finished(bot.db, reading["id"], _finished_datetime(when), book["pages"])
    line = voice.say("finished_book", user=interaction.user.mention, title=book["title"])
    await _respond(interaction, reading, line, view=review_view(book_id))


async def mark_dnf(interaction: discord.Interaction, book_id: int, page: int | None) -> None:
    bot, voice = interaction.client, interaction.client.voice
    reading = await repo_reads.get_reading(bot.db, interaction.user.id, book_id)
    book = await repo.get_book(bot.db, book_id)
    if reading is None or book is None:
        await _send(interaction, voice.say("not_reading"), ephemeral=True)
        return
    if page is not None and book["pages"] and page > book["pages"]:
        await _send(interaction, voice.say("page_too_high", pages=book["pages"]), ephemeral=True)
        return
    await repo_reads.mark_dnf(bot.db, reading["id"], page)
    await _respond(interaction, reading, voice.say("did_not_finish", user=interaction.user.mention, title=book["title"]))
