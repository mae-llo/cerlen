"""Autocomplete lists for commands that take one of your own books, reads or notes."""

from __future__ import annotations

import discord
from discord import app_commands

from cerlen import repo, repo_reads
from cerlen.util import trim


def _choices(pairs) -> list[app_commands.Choice[str]]:
    return [app_commands.Choice(name=trim(name, 100), value=str(value)) for name, value in pairs][:25]


async def reads_autocomplete(interaction: discord.Interaction, current: str):
    rows = await repo_reads.active_reads(interaction.client.db, interaction.guild_id)
    current = current.lower()
    kind = {"book_of_the_month": "Book of the Month", "other_read": "Other read"}
    return _choices(
        (f"{r['title']} ({kind[r['kind']]})", r["id"]) for r in rows if current in r["title"].lower()
    )


async def my_reading_autocomplete(interaction: discord.Interaction, current: str):
    rows = await repo_reads.reading_choices(interaction.client.db, interaction.user.id, ("reading", "paused"), current)
    return _choices((r["title"], r["book_id"]) for r in rows)


async def my_paused_autocomplete(interaction: discord.Interaction, current: str):
    rows = await repo_reads.reading_choices(interaction.client.db, interaction.user.id, ("paused",), current)
    return _choices((r["title"], r["book_id"]) for r in rows)


async def my_any_reading_autocomplete(interaction: discord.Interaction, current: str):
    rows = await repo_reads.reading_choices(
        interaction.client.db, interaction.user.id, ("reading", "paused", "finished", "dnf"), current
    )
    return _choices((r["title"], r["book_id"]) for r in rows)


async def unreviewed_autocomplete(interaction: discord.Interaction, current: str):
    rows = await repo_reads.unreviewed_finished(interaction.client.db, interaction.user.id, current)
    return _choices((r["title"], r["book_id"]) for r in rows)


async def my_reviews_autocomplete(interaction: discord.Interaction, current: str):
    rows = await repo_reads.reviewed_books(interaction.client.db, interaction.user.id, current)
    return _choices((r["title"], r["book_id"]) for r in rows)


async def queue_autocomplete(interaction: discord.Interaction, current: str):
    rows = await repo_reads.queue_list(interaction.client.db, interaction.guild_id)
    current = current.lower()
    return _choices((f"{r['position']}. {r['title']}", r["book_id"]) for r in rows if current in r["title"].lower())


async def my_tbr_autocomplete(interaction: discord.Interaction, current: str):
    rows = await repo_reads.tbr_list(interaction.client.db, interaction.user.id)
    current = current.lower()
    return _choices((f"{r['position']}. {r['title']}", r["book_id"]) for r in rows if current in r["title"].lower())


async def tbr_then_search_autocomplete(interaction: discord.Interaction, current: str):
    """Your TBR first, then the book search."""
    rows = await repo_reads.tbr_list(interaction.client.db, interaction.user.id)
    current_l = current.lower().strip()
    mine = [
        app_commands.Choice(name=trim(r["title"], 100), value=f"db:{r['book_id']}")
        for r in rows
        if current_l in r["title"].lower()
    ][:5]
    if len(current_l) < 2 or interaction.client.books is None:
        return mine
    try:
        found = await interaction.client.books.suggest(current, limit=10)
    except Exception:
        return mine
    seen = {c.value for c in mine}
    extra = [app_commands.Choice(name=s.label[:100], value=s.value[:100]) for s in found if s.value not in seen]
    return (mine + extra)[:25]


async def logged_books_autocomplete(interaction: discord.Interaction, current: str):
    rows = await repo_reads.books_with_logs(interaction.client.db, None, current)
    return _choices((r["title"], r["book_id"]) for r in rows)


async def my_logs_autocomplete(interaction: discord.Interaction, current: str):
    rows = await repo_reads.my_logs(interaction.client.db, interaction.user.id, current)
    return _choices((f"{r['title']} p.{r['page']}: {r['text']}", r["id"]) for r in rows)


async def book_for(bot, value: str):
    """A saved book from an autocomplete value (a plain id, or 'db:ID' style)."""
    value = value.strip()
    if value.isdigit():
        return await repo.get_book(bot.db, int(value))
    book_id = await bot.books.resolve(value)
    return await repo.get_book(bot.db, book_id) if book_id else None


async def read_for(bot, guild_id: int, value: str | None):
    """The read named by an autocomplete value; with none given, the Book of the Month, or the only read."""
    if value and value.isdigit():
        read = await repo_reads.get_club_read(bot.db, int(value))
        return read if read and read["guild_id"] == guild_id else None
    reads = await repo_reads.active_reads(bot.db, guild_id)
    if not reads:
        return None
    botm = [r for r in reads if r["kind"] == "book_of_the_month"]
    return botm[0] if botm else reads[0]


async def finish_autocomplete(interaction: discord.Interaction, current: str):
    """Books you are reading first, then the book search (for books finished earlier)."""
    rows = await repo_reads.reading_choices(interaction.client.db, interaction.user.id, ("reading", "paused"), current)
    mine = [app_commands.Choice(name=trim(r["title"], 100), value=str(r["book_id"])) for r in rows][:8]
    if len(current.strip()) < 2 or interaction.client.books is None:
        return mine
    try:
        found = await interaction.client.books.suggest(current, limit=10)
    except Exception:
        return mine
    return (mine + [app_commands.Choice(name=s.label[:100], value=s.value[:100]) for s in found])[:25]
