"""Who counts as an admin: anyone with Manage Server, or holding the admin role."""

from __future__ import annotations

import discord
from discord import app_commands

from cerlen import repo


class NotAdmin(app_commands.CheckFailure):
    pass


async def user_is_admin(bot, user: discord.abc.User, guild_id: int | None) -> bool:
    if guild_id is None or not isinstance(user, discord.Member):
        return False
    if user.guild_permissions.manage_guild:
        return True
    settings = await repo.get_settings(bot.db, guild_id)
    role_id = settings["admin_role_id"]
    return bool(role_id) and any(role.id == role_id for role in user.roles)


def admin_only():
    """Use under a command decorator. Members get Cerlen's refusal instead."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if await user_is_admin(interaction.client, interaction.user, interaction.guild_id):
            return True
        raise NotAdmin()

    return app_commands.check(predicate)
