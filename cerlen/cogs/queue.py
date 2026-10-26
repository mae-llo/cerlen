"""/queue: the server TBR and picking the next book."""

from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

from cerlen import flows, repo, repo_reads
from cerlen.autocomplete import book_autocomplete
from cerlen.cards import EMBED_COLOR, build_book_embed
from cerlen.checks import admin_only
from cerlen.pickers import book_for, queue_autocomplete
from cerlen.util import trim
from cerlen.views import start_view

NO_PINGS = discord.AllowedMentions.none()


class QueueCog(commands.GroupCog, group_name="queue", group_description="The server's to-be-read queue."):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def _queued_book(self, interaction: discord.Interaction, value: str):
        row = await book_for(self.bot, value)
        queued = None
        if row:
            queued = next(
                (q for q in await repo_reads.queue_list(self.bot.db, interaction.guild_id) if q["book_id"] == row["id"]),
                None,
            )
        if queued is None:
            await interaction.response.send_message(self.bot.voice.say("not_in_queue"), ephemeral=True)
        return row if queued else None

    @app_commands.command(name="add", description="Add a book to the queue. (admin)")
    @app_commands.describe(book="The book", goodreads="Goodreads rating, 0 to 5", storygraph="StoryGraph rating, 0 to 5")
    @app_commands.autocomplete(book=book_autocomplete)
    @admin_only()
    @app_commands.guild_only()
    async def add(
        self,
        interaction: discord.Interaction,
        book: str,
        goodreads: app_commands.Range[float, 0, 5] | None = None,
        storygraph: app_commands.Range[float, 0, 5] | None = None,
    ) -> None:
        voice = self.bot.voice
        await interaction.response.defer()
        book_id = await self.bot.books.resolve(book)
        row = await repo.get_book(self.bot.db, book_id) if book_id else None
        if row is None:
            await interaction.followup.send(voice.say("book_not_found"), ephemeral=True)
            return
        if goodreads is not None or storygraph is not None:
            await repo.set_outside_ratings(
                self.bot.db,
                row["id"],
                goodreads if goodreads is not None else row["goodreads_rating"],
                storygraph if storygraph is not None else row["storygraph_rating"],
            )
        added, count = await repo.add_to_queue(self.bot.db, interaction.guild_id, row["id"], interaction.user.id)
        if added:
            await interaction.followup.send(voice.say("queue_added", title=row["title"], count=count))
        elif goodreads is not None or storygraph is not None:
            await interaction.followup.send(voice.say("ratings_saved"), ephemeral=True)
        else:
            await interaction.followup.send(voice.say("queue_exists", title=row["title"]), ephemeral=True)

    @app_commands.command(name="list", description="Show the queue.")
    @app_commands.guild_only()
    async def list(self, interaction: discord.Interaction) -> None:
        rows = await repo_reads.queue_list(self.bot.db, interaction.guild_id)
        if not rows:
            await interaction.response.send_message(self.bot.voice.say("queue_empty"), ephemeral=True)
            return
        lines = []
        for row in rows[:25]:
            pages = f", {row['pages']} pages" if row["pages"] else ""
            author = f" by {row['authors']}" if row["authors"] else ""
            lines.append(f"{row['position']}. **{trim(row['title'], 70)}**{author}{pages} (added by <@{row['added_by']}>)")
        await interaction.response.send_message(
            embed=discord.Embed(title="Queue", description="\n".join(lines), color=EMBED_COLOR),
            allowed_mentions=NO_PINGS,
        )

    @app_commands.command(name="remove", description="Remove a book from the queue. (admin)")
    @app_commands.autocomplete(book=queue_autocomplete)
    @admin_only()
    @app_commands.guild_only()
    async def remove(self, interaction: discord.Interaction, book: str) -> None:
        row = await self._queued_book(interaction, book)
        if row:
            await repo_reads.queue_remove(self.bot.db, interaction.guild_id, row["id"])
            await interaction.response.send_message(self.bot.voice.say("setting_saved"), ephemeral=True)

    @app_commands.command(name="move", description="Move a book to a new place in the queue. (admin)")
    @app_commands.autocomplete(book=queue_autocomplete)
    @admin_only()
    @app_commands.guild_only()
    async def move(self, interaction: discord.Interaction, book: str, position: app_commands.Range[int, 1, 500]) -> None:
        row = await self._queued_book(interaction, book)
        if row:
            await repo_reads.queue_move(self.bot.db, interaction.guild_id, row["id"], position)
            await interaction.response.send_message(self.bot.voice.say("setting_saved"), ephemeral=True)

    @app_commands.command(name="poll", description="Let the server vote on the next book. (admin)")
    @app_commands.describe(count="How many books from the front of the queue (2 to 10)", hours="Hours the poll stays open")
    @admin_only()
    @app_commands.guild_only()
    async def poll(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 2, 10] = 10,
        hours: app_commands.Range[int, 1, 336] = 24,
    ) -> None:
        voice = self.bot.voice
        if await repo_reads.open_poll(self.bot.db, interaction.guild_id):
            await interaction.response.send_message(voice.say("poll_open"), ephemeral=True)
            return
        rows = (await repo_reads.queue_list(self.bot.db, interaction.guild_id))[:count]
        if len(rows) < 2:
            await interaction.response.send_message(
                voice.say("queue_empty") if not rows else voice.say("poll_needs_two"), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        await flows.open_poll(interaction, rows, hours)
        await interaction.followup.send(voice.say("setting_saved"), ephemeral=True)

    @app_commands.command(name="poll-close", description="End the open poll now. (admin)")
    @admin_only()
    @app_commands.guild_only()
    async def poll_close(self, interaction: discord.Interaction) -> None:
        poll = await repo_reads.open_poll(self.bot.db, interaction.guild_id)
        if poll is None:
            await interaction.response.send_message(self.bot.voice.say("no_open_poll"), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await flows.close_poll(self.bot, poll)
        await interaction.followup.send(self.bot.voice.say("setting_saved"), ephemeral=True)

    async def _announce_pick(self, interaction: discord.Interaction, row, key: str) -> None:
        book = await repo.get_book(self.bot.db, row["book_id"])
        await interaction.response.send_message(
            self.bot.voice.say(key, title=row["title"]),
            embed=build_book_embed(book, ["Picked as the next read"]),
            view=start_view(row["book_id"]),
            allowed_mentions=NO_PINGS,
        )

    @app_commands.command(name="random", description="Pick a random book from the queue. (admin)")
    @admin_only()
    @app_commands.guild_only()
    async def random(self, interaction: discord.Interaction) -> None:
        rows = await repo_reads.queue_list(self.bot.db, interaction.guild_id)
        if not rows:
            await interaction.response.send_message(self.bot.voice.say("queue_empty"), ephemeral=True)
            return
        await self._announce_pick(interaction, random.choice(rows), "random_pick")

    @app_commands.command(name="next", description="Pick the book at the front of the queue. (admin)")
    @admin_only()
    @app_commands.guild_only()
    async def next(self, interaction: discord.Interaction) -> None:
        rows = await repo_reads.queue_list(self.bot.db, interaction.guild_id)
        if not rows:
            await interaction.response.send_message(self.bot.voice.say("queue_empty"), ephemeral=True)
            return
        await self._announce_pick(interaction, rows[0], "next_in_line")

    @app_commands.command(name="choose", description="Pick a specific queued book. (admin)")
    @app_commands.autocomplete(book=queue_autocomplete)
    @admin_only()
    @app_commands.guild_only()
    async def choose(self, interaction: discord.Interaction, book: str) -> None:
        row = await self._queued_book(interaction, book)
        if row:
            queued = next(
                q for q in await repo_reads.queue_list(self.bot.db, interaction.guild_id) if q["book_id"] == row["id"]
            )
            await self._announce_pick(interaction, queued, "chosen_by_admin")


async def setup(bot) -> None:
    await bot.add_cog(QueueCog(bot))
