"""/reading: your personal reading entries."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cerlen import repo, repo_reads
from cerlen.cards import EMBED_COLOR
from cerlen.format import progress_bar
from cerlen.pickers import (
    book_for,
    my_any_reading_autocomplete,
    my_paused_autocomplete,
    my_reading_autocomplete,
    tbr_then_search_autocomplete,
)
from cerlen.ui import confirm
from cerlen.util import trim

NO_PINGS = discord.AllowedMentions.none()
STATE = {"reading": "reading", "paused": "paused", "finished": "finished", "dnf": "dropped"}


class ReadingCog(commands.GroupCog, group_name="reading", group_description="Your personal reading entries."):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="start", description="Start reading a book of your own.")
    @app_commands.describe(book="Your TBR first, then a search")
    @app_commands.autocomplete(book=tbr_then_search_autocomplete)
    @app_commands.guild_only()
    async def start(self, interaction: discord.Interaction, book: str) -> None:
        voice = self.bot.voice
        await interaction.response.defer()
        book_id = await self.bot.books.resolve(book)
        row = await repo.get_book(self.bot.db, book_id) if book_id else None
        if row is None:
            await interaction.followup.send(voice.say("book_not_found"), ephemeral=True)
            return
        reading, created = await repo_reads.start_reading(self.bot.db, interaction.user.id, row["id"])
        if not created and reading["status"] in ("finished", "dnf"):
            await interaction.followup.send(voice.say("reading_closed", title=row["title"]), ephemeral=True)
            return
        await interaction.followup.send(
            voice.say("started_reading", user=interaction.user.mention, title=row["title"]), allowed_mentions=NO_PINGS
        )

    @app_commands.command(name="list", description="Show current and recent reads.")
    @app_commands.describe(user="Whose reads (yours if left out)")
    @app_commands.guild_only()
    async def list(self, interaction: discord.Interaction, user: discord.Member | None = None) -> None:
        member = user or interaction.user
        rows = await repo_reads.user_readings(self.bot.db, member.id)
        if not rows:
            await interaction.response.send_message(
                self.bot.voice.say("reading_empty", user=member.display_name), ephemeral=True
            )
            return
        lines = []
        for row in rows:
            if row["status"] in ("reading", "paused"):
                detail = f"{STATE[row['status']]}, {progress_bar(row['current_page'], row['pages'])}"
            else:
                detail = f"{STATE[row['status']]} {(row['finished_at'] or '')[:10]}".strip()
            lines.append(f"**{trim(row['title'], 60)}**: {detail}")
        await interaction.response.send_message(
            embed=discord.Embed(title=f"{member.display_name}'s reading", description="\n".join(lines), color=EMBED_COLOR)
        )

    async def _set_status(self, interaction: discord.Interaction, book: str, status: str, allowed: str) -> None:
        voice = self.bot.voice
        row = await book_for(self.bot, book)
        reading = await repo_reads.get_reading(self.bot.db, interaction.user.id, row["id"]) if row else None
        if reading is None or reading["status"] != allowed:
            await interaction.response.send_message(voice.say("not_reading"), ephemeral=True)
            return
        await repo_reads.set_reading_status(self.bot.db, reading["id"], status)
        await interaction.response.send_message(voice.say("noted"), ephemeral=True)

    @app_commands.command(name="pause", description="Pause a reading entry.")
    @app_commands.autocomplete(book=my_reading_autocomplete)
    @app_commands.guild_only()
    async def pause(self, interaction: discord.Interaction, book: str) -> None:
        await self._set_status(interaction, book, "paused", "reading")

    @app_commands.command(name="resume", description="Resume a paused entry.")
    @app_commands.autocomplete(book=my_paused_autocomplete)
    @app_commands.guild_only()
    async def resume(self, interaction: discord.Interaction, book: str) -> None:
        await self._set_status(interaction, book, "reading", "paused")

    @app_commands.command(name="remove", description="Delete an entry and its notes.")
    @app_commands.autocomplete(book=my_any_reading_autocomplete)
    @app_commands.guild_only()
    async def remove(self, interaction: discord.Interaction, book: str) -> None:
        row = await book_for(self.bot, book)
        reading = await repo_reads.get_reading(self.bot.db, interaction.user.id, row["id"]) if row else None
        if reading is None:
            await interaction.response.send_message(self.bot.voice.say("not_reading"), ephemeral=True)
            return
        if not await confirm(interaction, self.bot.voice.say("confirm_delete_reading", title=row["title"])):
            return
        await repo_reads.delete_reading(self.bot.db, reading["id"])
        await interaction.followup.send(self.bot.voice.say("noted"), ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(ReadingCog(bot))
