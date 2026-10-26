"""Buttons on the book card. They survive restarts because they carry the book id in their custom_id."""

from __future__ import annotations

import re

import discord

from cerlen import repo, repo_reads
from cerlen.checks import user_is_admin

ACTIONS = {
    "tbr": ("Add to my TBR", discord.ButtonStyle.secondary),
    "queue": ("Add to server TBR", discord.ButtonStyle.secondary),
    "start": ("Start club read", discord.ButtonStyle.primary),
    "ratings": ("Edit ratings", discord.ButtonStyle.secondary),
}
ADMIN_ACTIONS = {"queue", "start", "ratings"}


class BookButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cerlen:book:(?P<action>tbr|queue|start|ratings):(?P<book_id>\d+)"):
    def __init__(self, action: str, book_id: int):
        label, style = ACTIONS[action]
        super().__init__(discord.ui.Button(label=label, style=style, custom_id=f"cerlen:book:{action}:{book_id}"))
        self.action = action
        self.book_id = book_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):
        return cls(match["action"], int(match["book_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        bot = interaction.client
        voice = bot.voice

        if self.action in ADMIN_ACTIONS and not await user_is_admin(bot, interaction.user, interaction.guild_id):
            await interaction.response.send_message(voice.say("not_admin", user=interaction.user.mention), ephemeral=True)
            return

        book = await repo.get_book(bot.db, self.book_id)
        if book is None:
            await interaction.response.send_message(voice.say("book_not_found"), ephemeral=True)
            return

        if self.action == "tbr":
            added = await repo.add_to_user_tbr(bot.db, interaction.user.id, self.book_id)
            key = "tbr_added" if added else "tbr_exists"
            await interaction.response.send_message(
                voice.say(key, user=interaction.user.display_name, title=book["title"]), ephemeral=True
            )
        elif self.action == "queue":
            added, count = await repo.add_to_queue(bot.db, interaction.guild_id, self.book_id, interaction.user.id)
            key = "queue_added" if added else "queue_exists"
            await interaction.response.send_message(voice.say(key, title=book["title"], count=count), ephemeral=True)
        elif self.action == "start":
            await interaction.response.send_modal(StartReadModal(self.book_id))
        elif self.action == "ratings":
            await interaction.response.send_modal(RatingsModal(self.book_id, book))


def book_buttons(book_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for action in ACTIONS:
        view.add_item(BookButton(action, book_id))
    return view


class RatingsModal(discord.ui.Modal, title="Outside ratings"):
    def __init__(self, book_id: int, book):
        super().__init__()
        self.book_id = book_id
        self.goodreads = discord.ui.TextInput(
            label="Goodreads rating (0 to 5, blank to clear)",
            required=False,
            max_length=5,
            default="" if book["goodreads_rating"] is None else f"{book['goodreads_rating']:g}",
        )
        self.storygraph = discord.ui.TextInput(
            label="StoryGraph rating (0 to 5, blank to clear)",
            required=False,
            max_length=5,
            default="" if book["storygraph_rating"] is None else f"{book['storygraph_rating']:g}",
        )
        self.add_item(self.goodreads)
        self.add_item(self.storygraph)

    @staticmethod
    def _parse(text: str) -> float | None:
        text = text.strip()
        if not text:
            return None
        value = float(text)  # ValueError on junk
        if not 0 <= value <= 5:
            raise ValueError
        return round(value, 2)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        bot = interaction.client
        try:
            goodreads = self._parse(self.goodreads.value)
            storygraph = self._parse(self.storygraph.value)
        except ValueError:
            await interaction.response.send_message(bot.voice.say("invalid_outside_rating"), ephemeral=True)
            return
        await repo.set_outside_ratings(bot.db, self.book_id, goodreads, storygraph)
        await interaction.response.send_message(bot.voice.say("ratings_saved"), ephemeral=True)


class StartReadModal(discord.ui.Modal, title="Start a club read"):
    def __init__(self, book_id: int):
        super().__init__()
        self.book_id = book_id
        self.kind = discord.ui.TextInput(
            label="Type: Book of the Month or Other read", default="Book of the Month", max_length=30
        )
        self.deadline = discord.ui.TextInput(
            label="Deadline (YYYY-MM-DD, optional)", required=False, max_length=10, placeholder="2026-11-14"
        )
        self.add_item(self.kind)
        self.add_item(self.deadline)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from cerlen import flows
        from cerlen.format import parse_date

        voice = interaction.client.voice
        kind = "other_read" if "other" in self.kind.value.lower() else "book_of_the_month"
        deadline = None
        if self.deadline.value.strip():
            deadline = parse_date(self.deadline.value)
            if deadline is None:
                await interaction.response.send_message(voice.say("invalid_date"), ephemeral=True)
                return
        await interaction.response.defer(ephemeral=True)
        await flows.start_club_read(interaction, self.book_id, kind, deadline)


class JoinButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cerlen:join:(?P<read_id>\d+)"):
    def __init__(self, read_id: int):
        super().__init__(
            discord.ui.Button(label="Join", style=discord.ButtonStyle.success, custom_id=f"cerlen:join:{read_id}")
        )
        self.read_id = read_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):
        return cls(int(match["read_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        from cerlen import flows

        await flows.join_read(interaction, self.read_id)


class VoteButton(
    discord.ui.DynamicItem[discord.ui.Button], template=r"cerlen:vote:(?P<poll_id>\d+):(?P<book_id>\d+)"
):
    def __init__(self, poll_id: int, book_id: int, label: str = "Vote"):
        super().__init__(
            discord.ui.Button(
                label=label[:80], style=discord.ButtonStyle.primary, custom_id=f"cerlen:vote:{poll_id}:{book_id}"
            )
        )
        self.poll_id, self.book_id = poll_id, book_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):
        return cls(int(match["poll_id"]), int(match["book_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        bot = interaction.client
        book = await repo.get_book(bot.db, self.book_id)
        ok = await repo_reads.vote(bot.db, self.poll_id, interaction.user.id, self.book_id)
        key = "vote_saved" if ok else "poll_closed"
        await interaction.response.send_message(
            bot.voice.say(key, title=book["title"] if book else ""), ephemeral=True
        )


class FinishButton(discord.ui.DynamicItem[discord.ui.Button], template=r"cerlen:finish:(?P<book_id>\d+)"):
    def __init__(self, book_id: int):
        super().__init__(
            discord.ui.Button(
                label="Mark finished", style=discord.ButtonStyle.success, custom_id=f"cerlen:finish:{book_id}"
            )
        )
        self.book_id = book_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):
        return cls(int(match["book_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        from cerlen import progress_flow

        await progress_flow.mark_finished(interaction, self.book_id)


def start_view(book_id: int) -> discord.ui.View:
    """A single 'Start club read' button, shown to admins after a pick or a poll."""
    view = discord.ui.View(timeout=None)
    view.add_item(BookButton("start", book_id))
    return view


def join_view(read_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(JoinButton(read_id))
    return view


def poll_view(poll_id: int, books) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for index, book in enumerate(books, start=1):
        view.add_item(VoteButton(poll_id, book["book_id"], f"{index}. {book['title']}"))
    return view


def dynamic_items() -> tuple:
    from cerlen.logbook import LogNav
    from cerlen.review_flow import ReviewButton

    return (BookButton, JoinButton, VoteButton, FinishButton, LogNav, ReviewButton)
