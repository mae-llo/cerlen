"""/config: personal profile details for everyone, server settings for admins."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cerlen import repo
from cerlen.autocomplete import book_autocomplete
from cerlen.checks import admin_only
from cerlen.validation import (
    InvalidInput,
    clean_genre,
    clean_goodreads,
    clean_storygraph,
    parse_days,
    parse_time,
    parse_timezone,
)

_INVALID_LINES = {
    "storygraph": "invalid_name",
    "goodreads": "invalid_goodreads",
    "genre": "invalid_genre",
    "time": "invalid_time",
    "timezone": "invalid_timezone",
    "days": "invalid_days",
}


def _normalise_time(value: str) -> str:
    """Accept '9:00' as well as '09:00'."""
    value = value.strip()
    if len(value) == 4 and value[1] == ":":
        value = "0" + value
    return value


class ConfigCog(commands.GroupCog, group_name="config", group_description="Your profile details and server settings."):
    favorites = app_commands.Group(name="favorites", description="Your top 5 favorite books.")

    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    # --- helpers ----------------------------------------------------------

    async def _say(self, interaction: discord.Interaction, key: str, **values) -> None:
        await interaction.response.send_message(
            self.bot.voice.say(key, **values),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def _save_detail(self, interaction, field: str, value: str | None, cleaner) -> None:
        try:
            cleaned = cleaner(value) if value else None
        except InvalidInput as error:
            await self._say(interaction, _INVALID_LINES[str(error) or field])
            return
        await repo.set_profile_field(self.bot.db, interaction.user.id, field, cleaned)
        await self._say(interaction, "detail_saved" if cleaned else "detail_cleared")

    async def _save_setting(self, interaction, column: str, value) -> None:
        await repo.set_setting(self.bot.db, interaction.guild_id, column, value)
        await self._say(interaction, "setting_saved")

    # --- personal details -------------------------------------------------

    @app_commands.command(name="goodreads", description="Set your Goodreads username or profile link.")
    @app_commands.describe(value="Your username or https://www.goodreads.com/... link (leave empty to clear)")
    @app_commands.guild_only()
    async def goodreads(self, interaction: discord.Interaction, value: str | None = None) -> None:
        await self._save_detail(interaction, "goodreads", value, clean_goodreads)

    @app_commands.command(name="storygraph", description="Set your StoryGraph username.")
    @app_commands.describe(value="Your StoryGraph username (leave empty to clear)")
    @app_commands.guild_only()
    async def storygraph(self, interaction: discord.Interaction, value: str | None = None) -> None:
        await self._save_detail(interaction, "storygraph", value, clean_storygraph)

    @app_commands.command(name="genre", description="Set your favorite genre.")
    @app_commands.describe(value="For example: Fantasy (leave empty to clear)")
    @app_commands.guild_only()
    async def genre(self, interaction: discord.Interaction, value: str | None = None) -> None:
        await self._save_detail(interaction, "favorite_genre", value, clean_genre)

    @favorites.command(name="add", description="Add a book to your top 5 favorites.")
    @app_commands.describe(book="The book to add", position="Slot 1 to 5 (leave empty for the next free slot)")
    @app_commands.autocomplete(book=book_autocomplete)
    @app_commands.guild_only()
    async def favorites_add(
        self,
        interaction: discord.Interaction,
        book: str,
        position: app_commands.Range[int, 1, repo.MAX_FAVORITES] | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        voice = self.bot.voice
        book_id = await self.bot.books.resolve(book)
        row = await repo.get_book(self.bot.db, book_id) if book_id else None
        if row is None:
            await interaction.followup.send(voice.say("book_not_found"), ephemeral=True)
            return
        outcome = await repo.set_favorite(self.bot.db, interaction.user.id, row["id"], position)
        if outcome == "exists":
            text = voice.say("favorite_exists", title=row["title"])
        elif outcome == "full":
            text = voice.say("favorites_full")
        else:
            count = len(await repo.list_favorites(self.bot.db, interaction.user.id))
            text = voice.say("favorite_added", title=row["title"], count=count)
        await interaction.followup.send(text, ephemeral=True)

    @favorites.command(name="remove", description="Remove a book from your favorites.")
    @app_commands.describe(book="The favorite to remove")
    @app_commands.guild_only()
    async def favorites_remove(self, interaction: discord.Interaction, book: str) -> None:
        voice = self.bot.voice
        row = await repo.get_book(self.bot.db, int(book)) if book.isdigit() else None
        removed = row is not None and await repo.remove_favorite(self.bot.db, interaction.user.id, row["id"])
        if removed:
            await self._say(interaction, "favorite_removed", title=row["title"])
        else:
            await self._say(interaction, "favorite_missing")

    @favorites_remove.autocomplete("book")
    async def favorites_remove_choices(self, interaction: discord.Interaction, current: str):
        rows = await repo.list_favorites(self.bot.db, interaction.user.id)
        current = current.lower()
        return [
            app_commands.Choice(name=f"{row['slot']}. {row['title']}"[:100], value=str(row["book_id"]))
            for row in rows
            if current in row["title"].lower()
        ]

    # --- admin settings ---------------------------------------------------

    @app_commands.command(name="show", description="Show the server settings. (admin)")
    @admin_only()
    @app_commands.guild_only()
    async def show(self, interaction: discord.Interaction) -> None:
        s = await repo.get_settings(self.bot.db, interaction.guild_id)

        def channel(value):
            return f"<#{value}>" if value else "not set"

        role = f"<@&{s['admin_role_id']}>" if s["admin_role_id"] else "not set (Manage Server is enough)"
        embed = discord.Embed(title="Server settings", color=discord.Color.from_rgb(112, 128, 144))
        embed.add_field(name="Discussion channel", value=channel(s["discussion_channel_id"]), inline=False)
        embed.add_field(name="Reviews channel", value=channel(s["reviews_channel_id"]), inline=False)
        embed.add_field(name="Announcement channel", value=channel(s["announcement_channel_id"]), inline=False)
        embed.add_field(name="Admin role", value=role, inline=False)
        embed.add_field(
            name="Forum tags",
            value=f"{s['tag_book_of_the_month']} / {s['tag_other_reads']}",
            inline=False,
        )
        embed.add_field(
            name="Reminders",
            value=f"{s['reminder_time']} {s['reminder_timezone']}, days before: {s['reminder_days']}",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _set_channel(self, interaction, column: str, channel) -> None:
        me = interaction.guild.me
        if not channel.permissions_for(me).send_messages:
            await self._say(interaction, "no_permission", channel=channel.mention)
            return
        await self._save_setting(interaction, column, channel.id)

    @app_commands.command(name="discussion-channel", description="Where read discussions are posted. (admin)")
    @app_commands.describe(channel="A forum channel (preferred) or a text channel")
    @admin_only()
    @app_commands.guild_only()
    async def discussion_channel(
        self, interaction: discord.Interaction, channel: discord.ForumChannel | discord.TextChannel
    ) -> None:
        await self._set_channel(interaction, "discussion_channel_id", channel)

    @app_commands.command(name="reviews-channel", description="Where reviews are posted. (admin)")
    @admin_only()
    @app_commands.guild_only()
    async def reviews_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await self._set_channel(interaction, "reviews_channel_id", channel)

    @app_commands.command(name="announcement-channel", description="Where announcements are posted. (admin)")
    @admin_only()
    @app_commands.guild_only()
    async def announcement_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await self._set_channel(interaction, "announcement_channel_id", channel)

    @app_commands.command(name="admin-role", description="A role that counts as admin for Cerlen. (admin)")
    @app_commands.describe(role="The role (leave empty to clear)")
    @admin_only()
    @app_commands.guild_only()
    async def admin_role(self, interaction: discord.Interaction, role: discord.Role | None = None) -> None:
        await self._save_setting(interaction, "admin_role_id", role.id if role else None)

    @app_commands.command(name="forum-tags", description="Names of the two forum tags. (admin)")
    @app_commands.describe(book_of_the_month="Tag for the Book of the Month", other_reads="Tag for other reads")
    @admin_only()
    @app_commands.guild_only()
    async def forum_tags(
        self,
        interaction: discord.Interaction,
        book_of_the_month: app_commands.Range[str, 1, 20] | None = None,
        other_reads: app_commands.Range[str, 1, 20] | None = None,
    ) -> None:
        if book_of_the_month:
            await repo.set_setting(self.bot.db, interaction.guild_id, "tag_book_of_the_month", book_of_the_month)
        if other_reads:
            await repo.set_setting(self.bot.db, interaction.guild_id, "tag_other_reads", other_reads)
        await self._say(interaction, "setting_saved")

    @app_commands.command(name="reminder-time", description="When reminders go out. (admin)")
    @app_commands.describe(time="HH:MM on a 24-hour clock", timezone="For example America/New_York")
    @admin_only()
    @app_commands.guild_only()
    async def reminder_time(
        self, interaction: discord.Interaction, time: str, timezone: str | None = None
    ) -> None:
        try:
            clean_time = parse_time(_normalise_time(time))
            clean_zone = parse_timezone(timezone) if timezone else None
        except InvalidInput as error:
            await self._say(interaction, _INVALID_LINES[str(error)])
            return
        await repo.set_setting(self.bot.db, interaction.guild_id, "reminder_time", clean_time)
        if clean_zone:
            await repo.set_setting(self.bot.db, interaction.guild_id, "reminder_timezone", clean_zone)
        await self._say(interaction, "setting_saved")

    @app_commands.command(name="reminder-days", description="Days before a deadline to remind. (admin)")
    @app_commands.describe(days="For example 7,3,1,0 (0 is the due day)")
    @admin_only()
    @app_commands.guild_only()
    async def reminder_days(self, interaction: discord.Interaction, days: str) -> None:
        try:
            clean = parse_days(days)
        except InvalidInput:
            await self._say(interaction, "invalid_days")
            return
        await self._save_setting(interaction, "reminder_days", clean)


async def setup(bot) -> None:
    await bot.add_cog(ConfigCog(bot))
