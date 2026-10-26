"""/progress: update your place, finish, or drop a book."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cerlen import progress_flow
from cerlen.format import parse_date
from cerlen.pickers import book_for, finish_autocomplete, my_reading_autocomplete


class ProgressCog(commands.GroupCog, group_name="progress", group_description="Your reading progress."):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="update", description="Save your place in a book.")
    @app_commands.describe(book="The book you are reading", page="Your current page", percent="Or how far through, in percent")
    @app_commands.autocomplete(book=my_reading_autocomplete)
    @app_commands.guild_only()
    async def update(
        self,
        interaction: discord.Interaction,
        book: str,
        page: app_commands.Range[int, 0, 20000] | None = None,
        percent: app_commands.Range[int, 0, 100] | None = None,
    ) -> None:
        row = await book_for(self.bot, book)
        if row is None:
            await interaction.response.send_message(self.bot.voice.say("book_not_found"), ephemeral=True)
            return
        await progress_flow.update_progress(interaction, row["id"], page, percent)

    @app_commands.command(name="finished", description="Mark a book finished.")
    @app_commands.describe(book="The book", date="If you finished it earlier, like 2026-09-30")
    @app_commands.autocomplete(book=finish_autocomplete)
    @app_commands.guild_only()
    async def finished(self, interaction: discord.Interaction, book: str, date: str | None = None) -> None:
        when = None
        if date:
            when = parse_date(date)
            if when is None:
                await interaction.response.send_message(self.bot.voice.say("invalid_date"), ephemeral=True)
                return
        if book.isdigit():
            book_id = int(book)
        else:
            await interaction.response.defer(ephemeral=True)  # a book search can take a moment
            book_id = await self.bot.books.resolve(book)
            if not book_id:
                await interaction.followup.send(self.bot.voice.say("book_not_found"), ephemeral=True)
                return
        await progress_flow.mark_finished(interaction, book_id, when)

    @app_commands.command(name="dnf", description="Mark a book did-not-finish. It gets no rating and is left out of stats.")
    @app_commands.describe(book="The book", page="The page you stopped at")
    @app_commands.autocomplete(book=my_reading_autocomplete)
    @app_commands.guild_only()
    async def dnf(
        self, interaction: discord.Interaction, book: str, page: app_commands.Range[int, 0, 20000] | None = None
    ) -> None:
        row = await book_for(self.bot, book)
        if row is None:
            await interaction.response.send_message(self.bot.voice.say("book_not_found"), ephemeral=True)
            return
        await progress_flow.mark_dnf(interaction, row["id"], page)


async def setup(bot) -> None:
    await bot.add_cog(ProgressCog(bot))
