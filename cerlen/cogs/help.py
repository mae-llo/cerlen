"""/help: lists the commands Cerlen currently has."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cerlen.cards import EMBED_COLOR


def _walk(commands_, prefix: str = ""):
    for command in commands_:
        name = f"{prefix}{command.name}"
        if isinstance(command, app_commands.Group):
            yield from _walk(command.commands, prefix=name + " ")
        else:
            yield name, command.description


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="List what Cerlen can do.")
    @app_commands.guild_only()
    async def help(self, interaction: discord.Interaction) -> None:
        entries = sorted(_walk(self.bot.tree.get_commands(guild=self.bot.guild_object)))
        lines = [f"`/{name}`: {description}" for name, description in entries]
        embed = discord.Embed(description="\n".join(lines)[:4000], color=EMBED_COLOR)
        embed.set_footer(text=self.bot.voice.say("help_footer"))
        await interaction.response.send_message(self.bot.voice.say("help_opening"), embed=embed, ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(HelpCog(bot))
