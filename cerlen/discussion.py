"""The read's discussion post: a forum post or a thread, created and used automatically."""

from __future__ import annotations

import logging

import discord

log = logging.getLogger(__name__)


async def get_thread(bot, read) -> discord.Thread | None:
    post_id = read["discussion_post_id"]
    if not post_id:
        return None
    guild = bot.get_guild(read["guild_id"])
    thread = guild.get_thread(post_id) if guild else None
    if thread is None:
        try:
            fetched = await bot.fetch_channel(post_id)
        except discord.HTTPException:
            return None
        thread = fetched if isinstance(fetched, discord.Thread) else None
    return thread


async def post(bot, read, content: str | None = None, **kwargs) -> discord.Message | None:
    """Post in the read's discussion post, re-opening it if it auto-archived."""
    thread = await get_thread(bot, read)
    if thread is None:
        return None
    try:
        if thread.archived:
            await thread.edit(archived=False)
        return await thread.send(content, **kwargs)
    except discord.HTTPException as error:
        log.warning("Could not post in discussion %s: %s", read["discussion_post_id"], error)
        return None


async def create(bot, guild: discord.Guild, settings, kind: str, title: str, opening: str, embed: discord.Embed):
    """Create the discussion post. Returns the thread, or None if it could not be made."""
    channel = guild.get_channel(settings["discussion_channel_id"]) if settings["discussion_channel_id"] else None
    name = title[:100]
    try:
        if isinstance(channel, discord.ForumChannel):
            tag_name = settings["tag_book_of_the_month"] if kind == "book_of_the_month" else settings["tag_other_reads"]
            tags = [t for t in channel.available_tags if t.name.lower() == tag_name.lower()]
            if not tags:
                log.warning("Forum %s has no tag named %r", channel, tag_name)
            created = await channel.create_thread(name=name, content=opening, embed=embed, applied_tags=tags[:1])
            return created.thread
        if isinstance(channel, discord.TextChannel):
            thread = await channel.create_thread(
                name=name, type=discord.ChannelType.public_thread, auto_archive_duration=10080
            )
            await thread.send(opening, embed=embed)
            return thread
    except discord.HTTPException as error:
        log.warning("Could not create the discussion post: %s", error)
    return None


async def add_member(bot, read, member: discord.abc.Snowflake) -> None:
    thread = await get_thread(bot, read)
    if thread:
        try:
            await thread.add_user(member)
        except discord.HTTPException:
            pass


async def remove_member(bot, read, member: discord.abc.Snowflake) -> None:
    thread = await get_thread(bot, read)
    if thread:
        try:
            await thread.remove_user(member)
        except discord.HTTPException:
            pass
