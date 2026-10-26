"""/club: start, join, finish and schedule club reads."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cerlen import discussion, flows, repo, repo_reads
from cerlen.autocomplete import book_autocomplete
from cerlen.cards import EMBED_COLOR
from cerlen.checks import admin_only
from cerlen.format import fmt_deadline, parse_date, progress_bar
from cerlen.pickers import read_for, reads_autocomplete
from cerlen.ui import confirm
from cerlen.util import trim
from cerlen.validation import InvalidInput, parse_days

KINDS = [
    app_commands.Choice(name="Book of the Month", value="book_of_the_month"),
    app_commands.Choice(name="Other read", value="other_read"),
]


class ClubCog(commands.GroupCog, group_name="club", group_description="Club reads."):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def _read_or_say(self, interaction: discord.Interaction, value: str | None):
        read = await read_for(self.bot, interaction.guild_id, value)
        if read is None:
            await interaction.response.send_message(self.bot.voice.say("no_active_reads"), ephemeral=True)
        return read

    @app_commands.command(name="start", description="Start a club read. (admin)")
    @app_commands.describe(
        book="The book",
        type="Book of the Month or an Other read",
        deadline="Optional date, like 2026-11-14",
        goodreads="Goodreads rating, 0 to 5 (optional)",
        storygraph="StoryGraph rating, 0 to 5 (optional)",
    )
    @app_commands.rename(kind="type")
    @app_commands.choices(kind=KINDS)
    @app_commands.autocomplete(book=book_autocomplete)
    @admin_only()
    @app_commands.guild_only()
    async def start(
        self,
        interaction: discord.Interaction,
        book: str,
        kind: app_commands.Choice[str],
        deadline: str | None = None,
        goodreads: app_commands.Range[float, 0, 5] | None = None,
        storygraph: app_commands.Range[float, 0, 5] | None = None,
    ) -> None:
        voice = self.bot.voice
        due = None
        if deadline:
            due = parse_date(deadline)
            if due is None:
                await interaction.response.send_message(voice.say("invalid_date"), ephemeral=True)
                return
        await interaction.response.defer(ephemeral=True)
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
        await flows.start_club_read(interaction, row["id"], kind.value, due)

    @app_commands.command(name="current", description="Show the active reads and everyone's progress.")
    @app_commands.guild_only()
    async def current(self, interaction: discord.Interaction) -> None:
        reads = await repo_reads.active_reads(self.bot.db, interaction.guild_id)
        if not reads:
            await interaction.response.send_message(self.bot.voice.say("no_active_reads"), ephemeral=True)
            return
        embeds = []
        for read in reads:
            embed = discord.Embed(title=trim(read["title"], 200), color=EMBED_COLOR)
            if read["cover_url"]:
                embed.set_thumbnail(url=read["cover_url"])
            kind = "Book of the Month" if read["kind"] == "book_of_the_month" else "Other read"
            embed.add_field(name="Type", value=kind, inline=True)
            embed.add_field(name="Deadline", value=fmt_deadline(read["deadline"]), inline=True)
            people = await repo_reads.participants(self.bot.db, read["id"])
            lines = []
            for person in people:
                if person["status"] == "finished":
                    state = "finished"
                elif person["status"] == "dnf":
                    state = "dropped"
                else:
                    state = progress_bar(person["current_page"], read["pages"])
                lines.append(f"<@{person['user_id']}> {state}")
            embed.add_field(name="Readers", value="\n".join(lines) or "No one has joined yet.", inline=False)
            embeds.append(embed)
        await interaction.response.send_message(embeds=embeds[:10], allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="join", description="Join a club read.")
    @app_commands.describe(read="Which read (the Book of the Month if left out)")
    @app_commands.autocomplete(read=reads_autocomplete)
    @app_commands.guild_only()
    async def join(self, interaction: discord.Interaction, read: str | None = None) -> None:
        row = await self._read_or_say(interaction, read)
        if row:
            await flows.join_read(interaction, row["id"])

    @app_commands.command(name="leave", description="Leave a club read.")
    @app_commands.describe(read="Which read (the Book of the Month if left out)")
    @app_commands.autocomplete(read=reads_autocomplete)
    @app_commands.guild_only()
    async def leave(self, interaction: discord.Interaction, read: str | None = None) -> None:
        row = await self._read_or_say(interaction, read)
        if row:
            await flows.leave_read(interaction, row["id"])

    @app_commands.command(name="history", description="Finished club reads.")
    @app_commands.describe(year="Only this year")
    @app_commands.guild_only()
    async def history(self, interaction: discord.Interaction, year: app_commands.Range[int, 2000, 2100] | None = None) -> None:
        rows = await repo_reads.read_history(self.bot.db, interaction.guild_id, year)
        if not rows:
            await interaction.response.send_message(self.bot.voice.say("no_history"), ephemeral=True)
            return
        from cerlen.ratings import format_rating

        lines = []
        for row in rows[:25]:
            kind = "BotM" if row["kind"] == "book_of_the_month" else "Other"
            finished = (row["finished_at"] or "")[:10]
            rating = format_rating(row["avg_units"]) if row["avg_units"] else "no ratings"
            lines.append(f"**{trim(row['title'], 60)}** ({kind}), {row['started_at'][:10]} to {finished}, {rating}")
        await interaction.response.send_message(
            embed=discord.Embed(description="\n".join(lines), color=EMBED_COLOR)
        )

    @app_commands.command(name="deadline", description="Set, change or clear a read's deadline. (admin)")
    @app_commands.describe(read="Which read", date="A date like 2026-11-14, or 'clear'")
    @app_commands.autocomplete(read=reads_autocomplete)
    @admin_only()
    @app_commands.guild_only()
    async def deadline(self, interaction: discord.Interaction, date: str, read: str | None = None) -> None:
        row = await self._read_or_say(interaction, read)
        if not row:
            return
        due = None
        if date.strip().lower() not in ("clear", "none", ""):
            due = parse_date(date)
            if due is None:
                await interaction.response.send_message(self.bot.voice.say("invalid_date"), ephemeral=True)
                return
        await flows.change_deadline(self.bot, row, due)
        await interaction.response.send_message(self.bot.voice.say("setting_saved"), ephemeral=True)

    @app_commands.command(name="reminders", description="Control reminders for one read. (admin)")
    @app_commands.describe(action="On, off, or send one now", read="Which read", days="For example 7,3,1,0")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="on", value="on"),
            app_commands.Choice(name="off", value="off"),
            app_commands.Choice(name="send now", value="now"),
        ]
    )
    @app_commands.autocomplete(read=reads_autocomplete)
    @admin_only()
    @app_commands.guild_only()
    async def reminders(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        read: str | None = None,
        days: str | None = None,
    ) -> None:
        row = await self._read_or_say(interaction, read)
        if not row:
            return
        voice = self.bot.voice
        clean = None
        if days:
            try:
                clean = parse_days(days)
            except InvalidInput:
                await interaction.response.send_message(voice.say("invalid_days"), ephemeral=True)
                return
        if action.value == "now":
            if not row["deadline"]:
                await interaction.response.send_message(voice.say("no_deadline"), ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            from datetime import date as _date, datetime
            from zoneinfo import ZoneInfo

            settings = await repo.get_settings(self.bot.db, interaction.guild_id)
            today = datetime.now(ZoneInfo(settings["reminder_timezone"])).date()
            left = max(0, (_date.fromisoformat(row["deadline"]) - today).days)
            count = await flows.send_reminders(self.bot, row, left)
            await interaction.followup.send(voice.say("reminders_sent", count=count), ephemeral=True)
            return
        await repo_reads.set_reminder_options(self.bot.db, row["id"], enabled=action.value == "on", days=clean)
        await interaction.response.send_message(voice.say("setting_saved"), ephemeral=True)

    @app_commands.command(name="finish", description="Close a read and post the summary and logbook. (admin)")
    @app_commands.autocomplete(read=reads_autocomplete)
    @admin_only()
    @app_commands.guild_only()
    async def finish(self, interaction: discord.Interaction, read: str | None = None) -> None:
        row = await read_for(self.bot, interaction.guild_id, read)
        if row is None:
            await interaction.response.send_message(self.bot.voice.say("no_active_reads"), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await flows.finish_club_read(interaction, row)
        await interaction.followup.send(self.bot.voice.say("read_finish_ack", title=row["title"]), ephemeral=True)

    @app_commands.command(name="cancel", description="Cancel a read. It never counts in stats. (admin)")
    @app_commands.autocomplete(read=reads_autocomplete)
    @admin_only()
    @app_commands.guild_only()
    async def cancel(self, interaction: discord.Interaction, read: str | None = None) -> None:
        row = await read_for(self.bot, interaction.guild_id, read)
        if row is None:
            await interaction.response.send_message(self.bot.voice.say("no_active_reads"), ephemeral=True)
            return
        if not await confirm(interaction, self.bot.voice.say("confirm_cancel", title=row["title"])):
            return
        await repo_reads.close_read(self.bot.db, row["id"], "cancelled")
        await discussion.post(self.bot, row, self.bot.voice.say("read_cancelled", title=row["title"]))
        await interaction.followup.send(self.bot.voice.say("setting_saved"), ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(ClubCog(bot))
