"""/stats: server statistics, or one book's."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cerlen import repo, repo_reads
from cerlen.autocomplete import book_autocomplete
from cerlen.cards import EMBED_COLOR
from cerlen.format import stars
from cerlen.ratings import format_rating
from cerlen.util import trim


def _hide(text: str) -> str:
    return "||" + text.replace("||", "| |") + "||"


class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Server stats, or the stats of one book.")
    @app_commands.describe(book="A book (leave out for the server stats)")
    @app_commands.autocomplete(book=book_autocomplete)
    @app_commands.guild_only()
    async def stats(self, interaction: discord.Interaction, book: str | None = None) -> None:
        if book:
            await interaction.response.defer()
            book_id = await self.bot.books.resolve(book)
            row = await repo.get_book(self.bot.db, book_id) if book_id else None
            if row is None:
                await interaction.followup.send(self.bot.voice.say("book_not_found"), ephemeral=True)
                return
            await interaction.followup.send(embed=await self._book_embed(row), allowed_mentions=discord.AllowedMentions.none())
        else:
            await interaction.response.send_message(
                embed=await self._server_embed(interaction.guild_id), allowed_mentions=discord.AllowedMentions.none()
            )

    async def _server_embed(self, guild_id: int) -> discord.Embed:
        s = await repo_reads.server_stats(self.bot.db, guild_id)
        embed = discord.Embed(title="Server stats", color=EMBED_COLOR)
        embed.add_field(name="Total Bookclub Books Read", value=str(s["club_books"]), inline=True)
        embed.add_field(name="Total Books read by the book club", value=str(s["unique_books"]), inline=True)
        embed.add_field(name="Total pages", value=f"{s['pages']:,}", inline=True)
        average = format_rating(s["average_units"]) if s["average_units"] else "no ratings yet"
        embed.add_field(name="Average club book rating", value=average, inline=False)
        if s["top"]:
            embed.add_field(
                name="Highest rated",
                value="\n".join(
                    f"{i}. {trim(r['title'], 60)} ({format_rating(r['avg_units'])})" for i, r in enumerate(s["top"], 1)
                ),
                inline=False,
            )
        if s["lowest"]:
            low = s["lowest"]
            embed.add_field(name="Lowest rated", value=f"{trim(low['title'], 60)} ({format_rating(low['avg_units'])})", inline=False)
        if s["readers"]:
            embed.add_field(
                name="Most active readers",
                value="\n".join(f"{i}. <@{r['user_id']}> ({r['n']} books)" for i, r in enumerate(s["readers"], 1)),
                inline=False,
            )
        return embed

    async def _book_embed(self, book) -> discord.Embed:
        s = await repo_reads.book_stats(self.bot.db, book["id"])
        embed = discord.Embed(title=trim(book["title"], 200), color=EMBED_COLOR)
        if book["cover_url"]:
            embed.set_thumbnail(url=book["cover_url"])
        embed.add_field(name="Finished by", value=str(s["finished"]), inline=True)
        embed.add_field(name="Ratings", value=str(len(s["reviews"])), inline=True)
        embed.add_field(
            name="Average", value=format_rating(s["average_units"]) if s["average_units"] else "no ratings yet", inline=True
        )
        if s["spread"]:
            embed.add_field(
                name="Spread",
                value="\n".join(f"{star}★ {'█' * n} {n}" for star, n in sorted(s["spread"].items(), reverse=True)),
                inline=False,
            )
        lines = []
        for review in s["reviews"][:15]:
            done = (review["finished_at"] or "")[:10]
            line = f"<@{review['user_id']}> {stars(review['units'])}" + (f", finished {done}" if done else "")
            if review["comment"]:
                comment = trim(review["comment"], 120)
                line += f"\n> {_hide(comment) if review['spoiler'] else comment}"
            lines.append(line)
        if lines:
            embed.add_field(name="Readers", value=trim("\n".join(lines), 1000), inline=False)
        return embed


async def setup(bot) -> None:
    await bot.add_cog(StatsCog(bot))
