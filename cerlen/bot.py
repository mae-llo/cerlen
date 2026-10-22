"""The Cerlen bot: wires the database, book lookups, voice and commands together."""

from __future__ import annotations

import logging

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import cerlen.voice_config  # noqa: F401  (adds extra default lines)
from cerlen import repo
from cerlen.books.service import BookService
from cerlen.checks import NotAdmin
from cerlen.db import Database
from cerlen.settings import Settings
from cerlen.voice import Voice

log = logging.getLogger(__name__)

EXTENSIONS = (
    "cerlen.cogs.book",
    "cerlen.cogs.profile",
    "cerlen.cogs.config",
    "cerlen.cogs.help",
)


class CerlenBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.default()
        intents.members = True  # needed for join dates and welcome lines (enable in the Developer Portal)
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None)
        self.settings = settings
        self.guild_object = discord.Object(id=settings.guild_id)
        self.db = Database(settings.database_path)
        self.voice = Voice(settings.voice_path)
        self.http_session: aiohttp.ClientSession | None = None
        self.books: BookService | None = None
        self.tree.on_error = self.on_tree_error

    async def setup_hook(self) -> None:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        await self.db.connect()

        contact = f" ({self.settings.contact})" if self.settings.contact else ""
        self.http_session = aiohttp.ClientSession(headers={"User-Agent": f"CerlenBookClubBot/0.1{contact}"})
        self.books = BookService(self.http_session, self.db)

        from cerlen.views import BookButton

        self.add_dynamic_items(BookButton)

        for extension in EXTENSIONS:
            await self.load_extension(extension)

        # Commands are synced to your one server only, so changes show up instantly.
        self.tree.copy_global_to(guild=self.guild_object)
        synced = await self.tree.sync(guild=self.guild_object)
        log.info("Synced %d commands to guild %s", len(synced), self.settings.guild_id)

    async def close(self) -> None:
        if self.http_session:
            await self.http_session.close()
        await self.db.close()
        await super().close()

    async def on_ready(self) -> None:
        log.info("Cerlen is ready as %s", self.user)
        if self.get_guild(self.settings.guild_id) is None:
            log.warning("Cerlen is not in the server with GUILD_ID %s. Check the ID and the invite.", self.settings.guild_id)

    async def on_member_join(self, member: discord.Member) -> None:
        if member.guild.id != self.settings.guild_id or member.bot:
            return
        settings = await repo.get_settings(self.db, member.guild.id)
        channel_id = settings["announcement_channel_id"]
        channel = member.guild.get_channel(channel_id) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(self.voice.say("welcome", user=member.mention))
            except discord.HTTPException:
                log.warning("Could not post the welcome line in %s", channel)

    async def on_tree_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, NotAdmin) or isinstance(error, app_commands.CheckFailure):
            text = self.voice.say("not_admin")
        else:
            log.exception("Command failed", exc_info=error)
            text = self.voice.say("error")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=True)
            else:
                await interaction.response.send_message(text, ephemeral=True)
        except discord.HTTPException:
            log.warning("Could not send the error message for a failed command.")
