"""/tbr: your personal to-be-read list."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cerlen import repo, repo_reads
from cerlen.autocomplete import book_autocomplete
from cerlen.cards import EMBED_COLOR
from cerlen.pickers import book_for, my_tbr_autocomplete
from cerlen.util import trim

NO_PINGS = discord.AllowedMentions.none()


class TbrCog(commands.GroupCog, group_name="tbr", group_description="Your to-be-read list."):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="add", description="Add a book to your TBR.")
    @app_commands.autocomplete(book=book_autocomplete)
    @app_commands.guild_only()
    async def add(self, interaction: discord.Interaction, book: str) -> None:
        voice = self.bot.voice
        await interaction.response.defer()
        book_id = await self.bot.books.resolve(book)
        row = await repo.get_book(self.bot.db, book_id) if book_id else None
        if row is None:
            await interaction.followup.send(voice.say("book_not_found"), ephemeral=True)
            return
        added = await repo.add_to_user_tbr(self.bot.db, interaction.user.id, row["id"])
        if added:
            await interaction.followup.send(
                voice.say("tbr_added", user=interaction.user.mention, title=row["title"]), allowed_mentions=NO_PINGS
            )
        else:
            await interaction.followup.send(voice.say("tbr_exists", title=row["title"]), ephemeral=True)

    @app_commands.command(name="list", description="Show a TBR.")
    @app_commands.describe(user="Whose TBR (yours if left out)")
    @app_commands.guild_only()
    async def list(self, interaction: discord.Interaction, user: discord.Member | None = None) -> None:
        member = user or interaction.user
        rows = await repo_reads.tbr_list(self.bot.db, member.id)
        if not rows:
            await interaction.response.send_message(self.bot.voice.say("tbr_empty", user=member.display_name), ephemeral=True)
            return
        lines = []
        for row in rows[:25]:
            author = f" by {row['authors']}" if row["authors"] else ""
            lines.append(f"{row['position']}. **{trim(row['title'], 70)}**{author}")
        embed = discord.Embed(title=f"{member.display_name}'s TBR", description="\n".join(lines), color=EMBED_COLOR)
        if len(rows) > 25:
            embed.set_footer(text=f"Showing 25 of {len(rows)}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="remove", description="Remove a book from your TBR.")
    @app_commands.autocomplete(book=my_tbr_autocomplete)
    @app_commands.guild_only()
    async def remove(self, interaction: discord.Interaction, book: str) -> None:
        row = await book_for(self.bot, book)
        if row and await repo_reads.tbr_remove(self.bot.db, interaction.user.id, row["id"]):
            await interaction.response.send_message(self.bot.voice.say("noted"), ephemeral=True)
        else:
            await interaction.response.send_message(self.bot.voice.say("not_on_tbr"), ephemeral=True)

    @app_commands.command(name="move", description="Reorder your TBR.")
    @app_commands.autocomplete(book=my_tbr_autocomplete)
    @app_commands.guild_only()
    async def move(self, interaction: discord.Interaction, book: str, position: app_commands.Range[int, 1, 1000]) -> None:
        row = await book_for(self.bot, book)
        if row and await repo_reads.tbr_move(self.bot.db, interaction.user.id, row["id"], position):
            await interaction.response.send_message(self.bot.voice.say("noted"), ephemeral=True)
        else:
            await interaction.response.send_message(self.bot.voice.say("not_on_tbr"), ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(TbrCog(bot))
