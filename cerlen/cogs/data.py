"""/data: export or delete your own data."""

from __future__ import annotations

import io
import json

import discord
from discord import app_commands
from discord.ext import commands

from cerlen import repo, repo_reads
from cerlen.ui import confirm


class DataCog(commands.GroupCog, group_name="data", group_description="Your own data."):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="export", description="Download everything Cerlen holds about you.")
    @app_commands.guild_only()
    async def export(self, interaction: discord.Interaction) -> None:
        data = await repo_reads.export_user(self.bot.db, interaction.user.id)
        payload = json.dumps(data, indent=2, ensure_ascii=False, default=str).encode("utf-8")
        await interaction.response.send_message(
            self.bot.voice.say("data_exported"),
            file=discord.File(io.BytesIO(payload), filename="my-cerlen-data.json"),
            ephemeral=True,
        )

    @app_commands.command(name="delete", description="Delete everything Cerlen holds about you.")
    @app_commands.guild_only()
    async def delete(self, interaction: discord.Interaction) -> None:
        if not await confirm(interaction, self.bot.voice.say("confirm_delete_data")):
            return
        settings = await repo.get_settings(self.bot.db, interaction.guild_id)
        channel = interaction.guild.get_channel(settings["reviews_channel_id"]) if settings["reviews_channel_id"] else None
        if channel:
            for message_id in await repo_reads.user_review_messages(self.bot.db, interaction.user.id):
                try:
                    await (await channel.fetch_message(message_id)).delete()
                except discord.HTTPException:
                    pass
        await repo_reads.delete_user(self.bot.db, interaction.user.id)
        await interaction.followup.send(self.bot.voice.say("data_deleted"), ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(DataCog(bot))
