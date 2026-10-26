"""/review: rate 1 to 5 and comment."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cerlen import repo, repo_reads
from cerlen.checks import admin_only
from cerlen.pickers import book_for, my_reviews_autocomplete, unreviewed_autocomplete
from cerlen.ratings import rating_choices
from cerlen.review_flow import CommentModal
from cerlen.ui import confirm


class ReviewCog(commands.GroupCog, group_name="review", group_description="Rate and review books."):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def _delete(self, interaction: discord.Interaction, user_id: int, book_id: int) -> bool:
        review = await repo_reads.get_review(self.bot.db, user_id, book_id)
        if review is None:
            return False
        settings = await repo.get_settings(self.bot.db, interaction.guild_id)
        channel = interaction.guild.get_channel(settings["reviews_channel_id"]) if settings["reviews_channel_id"] else None
        if review["message_id"] and channel:
            try:
                await (await channel.fetch_message(review["message_id"])).delete()
            except discord.HTTPException:
                pass
        await repo_reads.delete_review(self.bot.db, review["id"])
        return True

    @app_commands.command(name="add", description="Review a book you have finished.")
    @app_commands.describe(book="A finished book you have not reviewed", rating="1 to 5 stars", spoiler="Hide the review behind a spoiler")
    @app_commands.choices(rating=rating_choices())
    @app_commands.autocomplete(book=unreviewed_autocomplete)
    @app_commands.guild_only()
    async def add(
        self, interaction: discord.Interaction, book: str, rating: app_commands.Choice[float], spoiler: bool = False
    ) -> None:
        row = await book_for(self.bot, book)
        if row is None:
            await interaction.response.send_message(self.bot.voice.say("book_not_found"), ephemeral=True)
            return
        await interaction.response.send_modal(CommentModal(row["id"], rating.value, spoiler))

    @app_commands.command(name="edit", description="Change one of your reviews.")
    @app_commands.describe(book="The book", rating="New rating (leave out to keep it)", spoiler="Hide the review behind a spoiler")
    @app_commands.choices(rating=rating_choices())
    @app_commands.autocomplete(book=my_reviews_autocomplete)
    @app_commands.guild_only()
    async def edit(
        self,
        interaction: discord.Interaction,
        book: str,
        rating: app_commands.Choice[float] | None = None,
        spoiler: bool | None = None,
    ) -> None:
        row = await book_for(self.bot, book)
        review = await repo_reads.get_review(self.bot.db, interaction.user.id, row["id"]) if row else None
        if review is None:
            await interaction.response.send_message(self.bot.voice.say("no_review"), ephemeral=True)
            return
        value = rating.value if rating else review["rating_units"] / 4
        keep_spoiler = bool(review["spoiler"]) if spoiler is None else spoiler
        await interaction.response.send_modal(CommentModal(row["id"], value, keep_spoiler, review["comment"]))

    @app_commands.command(name="delete", description="Delete your own review.")
    @app_commands.autocomplete(book=my_reviews_autocomplete)
    @app_commands.guild_only()
    async def delete(self, interaction: discord.Interaction, book: str) -> None:
        row = await book_for(self.bot, book)
        if row is None or await repo_reads.get_review(self.bot.db, interaction.user.id, row["id"]) is None:
            await interaction.response.send_message(self.bot.voice.say("no_review"), ephemeral=True)
            return
        if not await confirm(interaction, self.bot.voice.say("confirm_delete_review", title=row["title"])):
            return
        await self._delete(interaction, interaction.user.id, row["id"])
        await interaction.followup.send(self.bot.voice.say("noted"), ephemeral=True)

    @app_commands.command(name="remove", description="Delete someone else's review. (admin)")
    @app_commands.describe(book="The book", user="Whose review")
    @admin_only()
    @app_commands.guild_only()
    async def remove(self, interaction: discord.Interaction, book: str, user: discord.Member) -> None:
        row = await book_for(self.bot, book)
        if row is None or not await self._delete(interaction, user.id, row["id"]):
            await interaction.response.send_message(self.bot.voice.say("no_review"), ephemeral=True)
            return
        await interaction.response.send_message(self.bot.voice.say("noted"), ephemeral=True)

    @remove.autocomplete("book")
    async def remove_book_choices(self, interaction: discord.Interaction, current: str):
        from cerlen.autocomplete import book_autocomplete

        return await book_autocomplete(interaction, current)


async def setup(bot) -> None:
    await bot.add_cog(ReviewCog(bot))
