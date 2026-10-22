"""/profile: a member's card, with their details and reading stats."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cerlen import repo
from cerlen.cards import build_profile_embed, has_profile_details
from cerlen.stats import user_stats
from cerlen.util import utcnow


class ProfileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Show a member's reading profile.")
    @app_commands.describe(user="Whose profile to show (you, if left out)")
    @app_commands.guild_only()
    async def profile(self, interaction: discord.Interaction, user: discord.Member | None = None) -> None:
        member = user or interaction.user
        db = self.bot.db
        now = utcnow()
        profile = await repo.get_profile(db, member.id)
        favorites = await repo.list_favorites(db, member.id)
        stats = await user_stats(db, member.id, now)
        embed = build_profile_embed(member, profile, favorites, stats, now)

        key = "profile_intro" if has_profile_details(profile, favorites) else "profile_empty"
        await interaction.response.send_message(
            self.bot.voice.say(key, user=member.display_name),
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot) -> None:
    await bot.add_cog(ProfileCog(bot))
