"""The multi-step things Cerlen does: starting and finishing reads, polls, reminders."""

from __future__ import annotations

import logging
import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import discord

from cerlen import discussion, repo, repo_reads
from cerlen.cards import EMBED_COLOR, build_book_embed
from cerlen.format import fmt_deadline, progress_text
from cerlen.logbook import build_page
from cerlen.review_flow import review_view
from cerlen.util import trim, utcnow

log = logging.getLogger(__name__)

KIND_NAMES = {"book_of_the_month": "Book of the Month", "other_read": "Other read"}
NO_PINGS = discord.AllowedMentions.none()


def _guild(bot) -> discord.Guild | None:
    return bot.get_guild(bot.settings.guild_id)


async def _announcement_channel(bot, guild: discord.Guild, settings, fallback):
    channel = guild.get_channel(settings["announcement_channel_id"]) if settings["announcement_channel_id"] else None
    return channel if isinstance(channel, discord.TextChannel) else fallback


# --- starting a read ---------------------------------------------------------------


async def start_club_read(
    interaction: discord.Interaction, book_id: int, kind: str, deadline: date | None
) -> None:
    """Creates the read, announces it, and makes its discussion post.

    The interaction must already be deferred (ephemeral), so the admin gets a private reply.
    """
    from cerlen.views import join_view

    bot, voice = interaction.client, interaction.client.voice
    guild = interaction.guild
    settings = await repo.get_settings(bot.db, guild.id)
    book = await repo.get_book(bot.db, book_id)
    if book is None:
        await interaction.followup.send(voice.say("book_not_found"), ephemeral=True)
        return
    if not settings["discussion_channel_id"] or guild.get_channel(settings["discussion_channel_id"]) is None:
        await interaction.followup.send(voice.say("no_discussion_channel"), ephemeral=True)
        return
    if await repo_reads.active_read_for_book(bot.db, guild.id, book_id):
        await interaction.followup.send(voice.say("already_running", title=book["title"]), ephemeral=True)
        return
    if kind == "book_of_the_month" and await repo_reads.active_botm(bot.db, guild.id):
        await interaction.followup.send(voice.say("botm_running"), ephemeral=True)
        return

    deadline_text = deadline.isoformat() if deadline else None
    read_id = await repo_reads.create_club_read(bot.db, guild.id, book_id, kind, deadline_text)
    await repo_reads.queue_remove(bot.db, guild.id, book_id)
    await _skip_past_reminders(bot, settings, read_id, deadline)

    values = dict(
        title=book["title"],
        author=book["authors"] or "an unknown author",
        pages=book["pages"] or "an unknown number of",
        deadline=fmt_deadline(deadline_text),
    )
    intro = voice.say("botm_intro" if kind == "book_of_the_month" else "other_intro", **values)
    status = [f"Current {KIND_NAMES[kind]}"]
    card = build_book_embed(book, status)
    card.add_field(name="Type", value=KIND_NAMES[kind], inline=True)
    card.add_field(name="Deadline", value=values["deadline"], inline=True)

    channel = await _announcement_channel(bot, guild, settings, interaction.channel)
    announcement = await channel.send(
        f"{intro}\n\n{voice.say('join_prompt', title=book['title'])}",
        embed=card,
        view=join_view(read_id),
        allowed_mentions=NO_PINGS,
    )

    thread_card = build_book_embed(book, status)
    thread = await discussion.create(
        bot, guild, settings, kind, book["title"], voice.say("forum_welcome", **values), thread_card
    )
    await repo_reads.set_read_posts(bot.db, read_id, thread.id if thread else None, announcement.id)

    where = f"Discussion: {thread.mention}" if thread else "I could not create the discussion post. Check my permissions."
    await interaction.followup.send(voice.say("read_started", title=book["title"], link=where), ephemeral=True)


async def _skip_past_reminders(bot, settings, read_id: int, deadline: date | None) -> None:
    """Reminder days that already passed when a read starts are not 'missed'."""
    if deadline is None:
        return
    await repo_reads.clear_reminders(bot.db, read_id)
    today = datetime.now(ZoneInfo(settings["reminder_timezone"])).date()
    days_left = (deadline - today).days
    schedule = [int(x) for x in settings["reminder_days"].split(",")]
    await repo_reads.mark_reminders(bot.db, read_id, [d for d in schedule if d > days_left])


async def change_deadline(bot, read, deadline: date | None) -> None:
    settings = await repo.get_settings(bot.db, read["guild_id"])
    await repo_reads.set_deadline(bot.db, read["id"], deadline.isoformat() if deadline else None)
    await repo_reads.clear_reminders(bot.db, read["id"])
    if deadline:
        today = datetime.now(ZoneInfo(settings["reminder_timezone"])).date()
        schedule = [int(x) for x in (read["reminder_days"] or settings["reminder_days"]).split(",")]
        await repo_reads.mark_reminders(bot.db, read["id"], [d for d in schedule if d > (deadline - today).days])
    fresh = await repo_reads.get_club_read(bot.db, read["id"])
    await discussion.post(
        bot,
        fresh,
        bot.voice.say("deadline_changed", title=read["title"], deadline=fmt_deadline(deadline.isoformat() if deadline else None)),
        allowed_mentions=NO_PINGS,
    )


# --- joining and leaving ---------------------------------------------------------------------


async def join_read(interaction: discord.Interaction, read_id: int) -> None:
    bot, voice = interaction.client, interaction.client.voice
    read = await repo_reads.get_club_read(bot.db, read_id)
    if read is None or read["status"] != "active":
        await interaction.response.send_message(voice.say("read_closed"), ephemeral=True)
        return
    existing = await repo_reads.get_reading(bot.db, interaction.user.id, read["book_id"])
    if existing and existing["club_read_id"] == read_id:
        await interaction.response.send_message(voice.say("already_joined", title=read["title"]), ephemeral=True)
        return
    await repo_reads.start_reading(bot.db, interaction.user.id, read["book_id"], read_id)
    await discussion.add_member(bot, read, interaction.user)
    await discussion.post(
        bot, read, voice.say("member_joined", user=interaction.user.mention, title=read["title"]), allowed_mentions=NO_PINGS
    )
    await interaction.response.send_message(voice.say("join_ack", title=read["title"]), ephemeral=True)


async def leave_read(interaction: discord.Interaction, read_id: int) -> None:
    bot, voice = interaction.client, interaction.client.voice
    read = await repo_reads.get_club_read(bot.db, read_id)
    if read is None or not await repo_reads.leave_read(bot.db, interaction.user.id, read_id):
        await interaction.response.send_message(voice.say("not_in_read"), ephemeral=True)
        return
    await discussion.remove_member(bot, read, interaction.user)
    await discussion.post(
        bot, read, voice.say("member_left", user=interaction.user.mention, title=read["title"]), allowed_mentions=NO_PINGS
    )
    await interaction.response.send_message(voice.say("leave_ack", title=read["title"]), ephemeral=True)


# --- finishing a read -----------------------------------------------------------------------


async def finish_club_read(interaction: discord.Interaction, read) -> None:
    """Closes the read, posts the summary with a Review button, then the logbook. Interaction is deferred."""
    bot, voice = interaction.client, interaction.client.voice
    guild = interaction.guild
    settings = await repo.get_settings(bot.db, guild.id)
    people = await repo_reads.participants(bot.db, read["id"])
    finished = [p for p in people if p["status"] == "finished"]
    dropped = [p for p in people if p["status"] == "dnf"]
    await repo_reads.close_read(bot.db, read["id"], "finished")

    embed = discord.Embed(title=trim(read["title"], 200), color=EMBED_COLOR)
    embed.add_field(
        name="Finished",
        value="\n".join(f"<@{p['user_id']}>" for p in finished) or "No one",
        inline=False,
    )
    if dropped:
        embed.add_field(name="Did not finish", value="\n".join(f"<@{p['user_id']}>" for p in dropped), inline=False)
    if read["cover_url"]:
        embed.set_thumbnail(url=read["cover_url"])

    channel = await _announcement_channel(bot, guild, settings, interaction.channel)
    await channel.send(
        f"{voice.say('read_finished', title=read['title'], count=len(finished))}\n\n"
        f"{voice.say('review_prompt', title=read['title'])}",
        embed=embed,
        view=review_view(read["book_id"]),
        allowed_mentions=NO_PINGS,
    )
    await post_logbook(bot, read)


async def post_logbook(bot, read) -> None:
    voice = bot.voice
    entries = await repo_reads.list_logs(bot.db, read["book_id"])
    if not entries:
        await discussion.post(bot, read, voice.say("logbook_empty", title=read["title"]))
        return
    page = await build_page(bot, read["book_id"], 0, 0)
    embed, view = page
    await discussion.post(
        bot,
        read,
        voice.say("logbook_intro", title=read["title"], count=len(entries)),
        embed=embed,
        view=view,
        allowed_mentions=NO_PINGS,
    )


# --- polls ------------------------------------------------------------------------------------------


async def open_poll(interaction: discord.Interaction, book_rows, hours: int) -> None:
    from cerlen.views import poll_view

    bot, voice = interaction.client, interaction.client.voice
    guild = interaction.guild
    settings = await repo.get_settings(bot.db, guild.id)
    closes = utcnow() + timedelta(hours=hours)
    channel = await _announcement_channel(bot, guild, settings, interaction.channel)
    poll_id = await repo_reads.create_poll(bot.db, guild.id, channel.id, closes, [r["book_id"] for r in book_rows])

    local = closes.astimezone(ZoneInfo(settings["reminder_timezone"]))
    deadline = local.strftime("%A %d %B, %I:%M %p").replace(" 0", " ")
    embed = discord.Embed(
        description="\n".join(
            f"**{trim(r['title'], 80)}**" + (f" by {r['authors']}" if r["authors"] else "") for r in book_rows
        ),
        color=EMBED_COLOR,
    )
    message = await channel.send(
        voice.say("poll_opened", count=len(book_rows), deadline=deadline),
        embed=embed,
        view=poll_view(poll_id, book_rows),
        allowed_mentions=NO_PINGS,
    )
    await repo_reads.set_poll_message(bot.db, poll_id, message.id)


async def close_poll(bot, poll) -> bool:
    """Tallies the poll, announces the winner (breaking a tie at random) and offers the start form."""
    from cerlen.views import start_view

    voice = bot.voice
    options = await repo_reads.poll_options(bot.db, poll["id"])
    if not options:
        await repo_reads.close_poll(bot.db, poll["id"], None)
        return False
    top = max(o["votes"] for o in options)
    leaders = [o for o in options if o["votes"] == top]
    winner = random.choice(leaders)
    await repo_reads.close_poll(bot.db, poll["id"], winner["book_id"])

    guild = _guild(bot)
    channel = guild.get_channel(poll["channel_id"]) if guild else None
    if channel is None:
        return True
    key = "poll_tie" if len(leaders) > 1 else "poll_result"
    book = await repo.get_book(bot.db, winner["book_id"])
    if poll["message_id"]:
        try:
            old = await channel.fetch_message(poll["message_id"])
            await old.edit(view=None)
        except discord.HTTPException:
            pass
    await channel.send(
        voice.say(key, title=winner["title"], count=top),
        embed=build_book_embed(book, ["Chosen by poll"]),
        view=start_view(winner["book_id"]),
        allowed_mentions=NO_PINGS,
    )
    return True


# --- reminders -----------------------------------------------------------------------------------------


def _reminder_key(days_left: int) -> str:
    if days_left <= 0:
        return "reminder_due"
    if days_left == 1:
        return "reminder_1"
    return "reminder_3" if days_left <= 3 else "reminder_7"


async def send_reminders(bot, read, days_left: int, catchup: bool = False) -> int:
    """Pings only the members who have not finished. Returns how many were reminded."""
    voice = bot.voice
    people = [p for p in await repo_reads.participants(bot.db, read["id"]) if p["status"] in ("reading", "paused")]
    if not people:
        return 0
    allowed = discord.AllowedMentions(users=True)
    if catchup:
        mentions = " ".join(f"<@{p['user_id']}>" for p in people)
        line = voice.say("reminder_catchup", title=read["title"], days_left=days_left)
        await discussion.post(bot, read, f"{line}\n{mentions}", allowed_mentions=allowed)
        return len(people)
    key = _reminder_key(days_left)
    for person in people:
        await discussion.post(
            bot,
            read,
            voice.say(
                key,
                user=f"<@{person['user_id']}>",
                title=read["title"],
                days_left=days_left,
                progress=progress_text(person["current_page"], read["pages"]),
            ),
            allowed_mentions=allowed,
        )
    return len(people)


async def process_reminders(bot, now: datetime | None = None) -> None:
    """Runs every minute. Sends each due reminder once; after downtime, one catch-up per read."""
    now = now or utcnow()
    guild_id = bot.settings.guild_id
    settings = await repo.get_settings(bot.db, guild_id)
    tz = ZoneInfo(settings["reminder_timezone"])
    local = now.astimezone(tz)
    hour, minute = (int(x) for x in settings["reminder_time"].split(":"))
    reached = (local.hour, local.minute) >= (hour, minute)

    for read in await repo_reads.active_reads(bot.db, guild_id):
        if not read["deadline"] or not read["reminders_enabled"] or not read["discussion_post_id"]:
            continue
        deadline = date.fromisoformat(read["deadline"])
        days_left = (deadline - local.date()).days
        if days_left < 0:
            continue
        schedule = [int(x) for x in (read["reminder_days"] or settings["reminder_days"]).split(",")]
        sent = await repo_reads.reminders_sent(bot.db, read["id"])
        started = datetime.fromisoformat(read["started_at"]).astimezone(tz).date()
        missed = [
            d for d in schedule
            if d > days_left and d not in sent and deadline - timedelta(days=d) >= started
        ]
        due = days_left in schedule and days_left not in sent and reached
        if due:
            await send_reminders(bot, read, days_left)
            await repo_reads.mark_reminders(bot.db, read["id"], missed + [days_left])
        elif missed:
            await send_reminders(bot, read, days_left, catchup=True)
            await repo_reads.mark_reminders(bot.db, read["id"], missed)

    for poll in await repo_reads.due_polls(bot.db):
        await close_poll(bot, poll)
