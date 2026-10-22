"""/book: look a book up by title or ISBN."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cerlen import repo
from cerlen.autocomplete import book_autocomplete
from cerlen.cards import build_book_embed
from cerlen.views import book_buttons


class BookCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="book", description="Look up a book by title or ISBN.")
    @app_commands.describe(book="A title, an author, or an ISBN")
    @app_commands.autocomplete(book=book_autocomplete)
    @app_commands.guild_only()
    async def book(self, interaction: discord.Interaction, book: str) -> None:
        await interaction.response.defer()
        book_id = await self.bot.books.resolve(book)
        row = await repo.get_book(self.bot.db, book_id) if book_id else None
        if row is None:
            await interaction.followup.send(self.bot.voice.say("book_not_found"), ephemeral=True)
            return
        status = await repo.book_status(self.bot.db, interaction.guild_id, row["id"], interaction.user.id)
        await interaction.followup.send(
            embed=build_book_embed(row, status), view=book_buttons(row["id"])
        )


async def setup(bot) -> None:
    await bot.add_cog(BookCog(bot))
