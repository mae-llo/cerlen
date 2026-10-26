"""/log: your diary notes on a book, and the logbook."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cerlen import repo, repo_reads
from cerlen.logbook import build_page
from cerlen.pickers import book_for, logged_books_autocomplete, my_logs_autocomplete, my_reading_autocomplete

NO_PINGS = discord.AllowedMentions.none()


class NoteModal(discord.ui.Modal, title="Log note"):
    def __init__(self, reading_id: int, book, page: int, spoiler: bool):
        super().__init__()
        self.reading_id, self.book, self.page, self.spoiler = reading_id, book, page, spoiler
        self.text = discord.ui.TextInput(label=f"Your note (page {page})", style=discord.TextStyle.paragraph, max_length=1500)
        self.add_item(self.text)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        bot = interaction.client
        await repo_reads.add_log(bot.db, self.reading_id, self.page, self.text.value.strip(), self.spoiler)
        await interaction.response.send_message(
            bot.voice.say("note_saved", user=interaction.user.mention, title=self.book["title"]),
            allowed_mentions=NO_PINGS,
        )


class LogCog(commands.GroupCog, group_name="log", group_description="Your notes on a book."):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="add", description="Write a diary note on a book.")
    @app_commands.describe(
        book="The book you are reading",
        page="Where in the book (your current page if left out)",
        spoiler="Hide the note behind a spoiler",
    )
    @app_commands.autocomplete(book=my_reading_autocomplete)
    @app_commands.guild_only()
    async def add(
        self,
        interaction: discord.Interaction,
        book: str,
        page: app_commands.Range[int, 0, 20000] | None = None,
        spoiler: bool = False,
    ) -> None:
        voice = self.bot.voice
        row = await book_for(self.bot, book)
        reading = await repo_reads.get_reading(self.bot.db, interaction.user.id, row["id"]) if row else None
        if reading is None:
            await interaction.response.send_message(voice.say("not_reading"), ephemeral=True)
            return
        where = reading["current_page"] if page is None else page
        if row["pages"] and where > row["pages"]:
            await interaction.response.send_message(voice.say("page_too_high", pages=row["pages"]), ephemeral=True)
            return
        await interaction.response.send_modal(NoteModal(reading["id"], row, where, spoiler))

    @app_commands.command(name="list", description="Flip through the logbook for a book.")
    @app_commands.describe(book="The book", user="Only this member's notes")
    @app_commands.autocomplete(book=logged_books_autocomplete)
    @app_commands.guild_only()
    async def list(self, interaction: discord.Interaction, book: str, user: discord.Member | None = None) -> None:
        row = await book_for(self.bot, book)
        if row is None:
            await interaction.response.send_message(self.bot.voice.say("book_not_found"), ephemeral=True)
            return
        page = await build_page(self.bot, row["id"], user.id if user else 0, 0)
        if page is None:
            await interaction.response.send_message(self.bot.voice.say("logbook_empty", title=row["title"]), ephemeral=True)
            return
        embed, view = page
        await interaction.response.send_message(embed=embed, view=view, allowed_mentions=NO_PINGS)

    @app_commands.command(name="delete", description="Delete one of your notes.")
    @app_commands.autocomplete(entry=my_logs_autocomplete)
    @app_commands.guild_only()
    async def delete(self, interaction: discord.Interaction, entry: str) -> None:
        if entry.isdigit() and await repo_reads.delete_log(self.bot.db, int(entry), interaction.user.id):
            await interaction.response.send_message(self.bot.voice.say("noted"), ephemeral=True)
        else:
            await interaction.response.send_message(self.bot.voice.say("no_note"), ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(LogCog(bot))
