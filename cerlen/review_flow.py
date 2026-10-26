"""Rating and reviewing: the form, the post in the reviews channel, and the link in the discussion."""

from __future__ import annotations

import logging
import re

import discord

from cerlen import discussion, repo, repo_reads
from cerlen.cards import EMBED_COLOR
from cerlen.format import stars
from cerlen.ratings import InvalidRating, format_rating, from_units, to_units
from cerlen.util import trim

log = logging.getLogger(__name__)


def review_embed(member: discord.abc.User, book, units: int, comment: str | None, spoiler: bool) -> discord.Embed:
    body = f"**{stars(units)}**"
    if comment:
        text = comment.replace("||", "| |")
        body += "\n\n" + (f"||{text}||" if spoiler else text)
    embed = discord.Embed(title=trim(book["title"], 200), description=body, color=EMBED_COLOR)
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    if spoiler:
        embed.set_footer(text="This review contains spoilers.")
    return embed


async def submit_review(
    interaction: discord.Interaction, book_id: int, rating: float, comment: str | None, spoiler: bool
) -> None:
    """Validates, posts or updates the review, links it from the discussion, and thanks the reviewer.

    The interaction must not have been answered yet.
    """
    bot, voice = interaction.client, interaction.client.voice
    try:
        units = to_units(rating)
    except InvalidRating:
        await interaction.response.send_message(voice.say("invalid_rating"), ephemeral=True)
        return

    book = await repo.get_book(bot.db, book_id)
    reading = await repo_reads.get_reading(bot.db, interaction.user.id, book_id)
    if book is None or reading is None or reading["status"] != "finished":
        await interaction.response.send_message(voice.say("review_need_finished"), ephemeral=True)
        return

    settings = await repo.get_settings(bot.db, interaction.guild_id)
    channel = interaction.guild.get_channel(settings["reviews_channel_id"]) if settings["reviews_channel_id"] else None
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message(voice.say("no_reviews_channel"), ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    comment = (comment or "").strip() or None
    existing = await repo_reads.get_review(bot.db, interaction.user.id, book_id)
    await repo_reads.save_review(bot.db, reading["id"], units, comment, spoiler)
    saved = await repo_reads.get_review(bot.db, interaction.user.id, book_id)
    embed = review_embed(interaction.user, book, units, comment, spoiler)

    message = None
    if existing and existing["message_id"]:
        try:
            message = await channel.fetch_message(existing["message_id"])
            await message.edit(embed=embed)
        except discord.HTTPException:
            message = None
    new_post = message is None
    if message is None:
        try:
            message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            await interaction.followup.send(voice.say("no_permission", channel=channel.mention), ephemeral=True)
            return
        await repo_reads.set_review_message(bot.db, saved["id"], message.id)

    if new_post and reading["club_read_id"]:
        read = await repo_reads.get_club_read(bot.db, reading["club_read_id"])
        if read:
            await discussion.post(
                bot,
                read,
                voice.say("review_link", user=interaction.user.mention, link=message.jump_url),
                allowed_mentions=discord.AllowedMentions.none(),
            )
    await interaction.followup.send(
        voice.say("review_thanks", user=interaction.user.mention, title=book["title"]), ephemeral=True
    )


class CommentModal(discord.ui.Modal, title="Your review"):
    def __init__(self, book_id: int, rating: float, spoiler: bool, current: str | None = None):
        super().__init__()
        self.book_id, self.rating, self.spoiler = book_id, rating, spoiler
        self.comment = discord.ui.TextInput(
            label="Comment (optional)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1500,
            default=current or None,
        )
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await submit_review(interaction, self.book_id, self.rating, self.comment.value, self.spoiler)


class RatingSelect(discord.ui.Select):
    def __init__(self, book_id: int):
        options = [
            discord.SelectOption(label=f"{format_rating(u)} stars", value=str(u)) for u in range(20, 3, -1)
        ]
        super().__init__(placeholder="Choose a rating", options=options)
        self.book_id = book_id

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ReviewView = self.view  # type: ignore[assignment]
        existing = await repo_reads.get_review(interaction.client.db, interaction.user.id, self.book_id)
        await interaction.response.send_modal(
            CommentModal(self.book_id, from_units(int(self.values[0])), view.spoiler, existing["comment"] if existing else None)
        )


class ReviewView(discord.ui.View):
    """Private rating picker shown from a Review button."""

    def __init__(self, book_id: int):
        super().__init__(timeout=300)
        self.spoiler = False
        self.add_item(RatingSelect(book_id))

    @discord.ui.button(label="Spoiler: off", style=discord.ButtonStyle.secondary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.spoiler = not self.spoiler
        button.label = "Spoiler: on" if self.spoiler else "Spoiler: off"
        await interaction.response.edit_message(view=self)


class ReviewButton(
    discord.ui.DynamicItem[discord.ui.Button], template=r"cerlen:review:(?P<book_id>\d+)"
):
    def __init__(self, book_id: int):
        super().__init__(
            discord.ui.Button(label="Review", style=discord.ButtonStyle.primary, custom_id=f"cerlen:review:{book_id}")
        )
        self.book_id = book_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):
        return cls(int(match["book_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        bot = interaction.client
        reading = await repo_reads.get_reading(bot.db, interaction.user.id, self.book_id)
        if reading is None or reading["status"] != "finished":
            await interaction.response.send_message(bot.voice.say("review_need_finished"), ephemeral=True)
            return
        book = await repo.get_book(bot.db, self.book_id)
        await interaction.response.send_message(
            bot.voice.say("review_prompt", title=book["title"] if book else "this book"),
            view=ReviewView(self.book_id),
            ephemeral=True,
        )


def review_view(book_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(ReviewButton(book_id))
    return view
