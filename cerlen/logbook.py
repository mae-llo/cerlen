"""The logbook: notes in book order, one per page, with Previous and Next buttons.

The buttons carry everything they need in their custom_id, so a logbook keeps
working after the bot restarts and long after the read has finished.
"""

from __future__ import annotations

import re

import discord

from cerlen import repo_reads
from cerlen.cards import EMBED_COLOR
from cerlen.util import trim


def _hide(text: str) -> str:
    return "||" + text.replace("||", "| |") + "||"


async def build_page(bot, book_id: int, user_id: int, index: int):
    """Returns (embed, view) for the note at `index`, or None if there are no notes."""
    entries = await repo_reads.list_logs(bot.db, book_id, user_id or None)
    if not entries:
        return None
    index = max(0, min(index, len(entries) - 1))
    entry = entries[index]
    text = trim(entry["text"], 3800)
    embed = discord.Embed(
        title=trim(entry["title"], 200),
        description=_hide(text) if entry["spoiler"] else text,
        color=EMBED_COLOR,
    )
    embed.add_field(name="Page", value=str(entry["page"]), inline=True)
    embed.add_field(name="Reader", value=f"<@{entry['user_id']}>", inline=True)
    embed.set_footer(text=f"Note {index + 1} of {len(entries)}")
    view = discord.ui.View(timeout=None)
    view.add_item(LogNav(book_id, user_id, index, "prev", disabled=index == 0))
    view.add_item(LogNav(book_id, user_id, index, "next", disabled=index >= len(entries) - 1))
    return embed, view


class LogNav(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"cerlen:log:(?P<book>\d+):(?P<user>\d+):(?P<index>\d+):(?P<dir>prev|next)",
):
    def __init__(self, book_id: int, user_id: int, index: int, direction: str, disabled: bool = False):
        label = "Previous" if direction == "prev" else "Next"
        super().__init__(
            discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.secondary,
                custom_id=f"cerlen:log:{book_id}:{user_id}:{index}:{direction}",
                disabled=disabled,
            )
        )
        self.book_id, self.user_id, self.index, self.direction = book_id, user_id, index, direction

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):
        return cls(int(match["book"]), int(match["user"]), int(match["index"]), match["dir"])

    async def callback(self, interaction: discord.Interaction) -> None:
        step = -1 if self.direction == "prev" else 1
        page = await build_page(interaction.client, self.book_id, self.user_id, self.index + step)
        if page is None:
            await interaction.response.send_message(interaction.client.voice.say("logbook_empty", title="this book"), ephemeral=True)
            return
        embed, view = page
        await interaction.response.edit_message(embed=embed, view=view)
