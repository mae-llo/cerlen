"""Builds the embeds and buttons the bot posts: the book card and the profile card."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

import aiosqlite
import discord
from discord.utils import escape_markdown

from cerlen.ratings import format_rating
from cerlen.stats import UserStats
from cerlen.util import humanize_duration, trim
from cerlen.validation import goodreads_link, storygraph_link

EMBED_COLOR = discord.Color.from_rgb(112, 128, 144)


# --- book card ------------------------------------------------------------


def goodreads_book_url(book: aiosqlite.Row) -> str:
    if book["isbn13"]:
        return f"https://www.goodreads.com/book/isbn/{book['isbn13']}"
    return "https://www.goodreads.com/search?q=" + quote(f"{book['title']} {book['authors']}".strip())


def storygraph_book_url(book: aiosqlite.Row) -> str:
    term = book["isbn13"] or f"{book['title']} {book['authors']}".strip()
    return "https://app.thestorygraph.com/browse?search_term=" + quote(term)


def _rating_text(value: float | None) -> str:
    if value is None:
        return "no rating entered"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def build_book_embed(book: aiosqlite.Row, status_lines: list[str]) -> discord.Embed:
    embed = discord.Embed(
        title=trim(book["title"], 250),
        description=trim(book["blurb"], 500) if book["blurb"] else None,
        color=EMBED_COLOR,
    )
    if book["cover_url"]:
        embed.set_thumbnail(url=book["cover_url"])

    embed.add_field(name="Author", value=escape_markdown(book["authors"] or "Unknown"), inline=True)
    embed.add_field(name="Pages", value=str(book["pages"]) if book["pages"] else "Unknown", inline=True)
    embed.add_field(name="Genre", value=escape_markdown(book["subjects"] or "Unknown"), inline=True)
    embed.add_field(name="Status", value="\n".join(status_lines), inline=False)
    embed.add_field(
        name="Goodreads",
        value=f"[View on Goodreads]({goodreads_book_url(book)}) · {_rating_text(book['goodreads_rating'])}",
        inline=True,
    )
    embed.add_field(
        name="StoryGraph",
        value=f"[View on StoryGraph]({storygraph_book_url(book)}) · {_rating_text(book['storygraph_rating'])}",
        inline=True,
    )
    if book["year"]:
        embed.set_footer(text=f"First published {book['year']}")
    return embed


# --- profile card ---------------------------------------------------------


def build_profile_embed(
    member: discord.Member,
    profile: aiosqlite.Row | None,
    favorites: list[aiosqlite.Row],
    stats: UserStats,
    now: datetime,
) -> discord.Embed:
    embed = discord.Embed(title=escape_markdown(member.display_name), color=EMBED_COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)

    if member.joined_at:
        span = humanize_duration(now - member.joined_at)
        embed.add_field(
            name="In the server",
            value=f"{span} (since {member.joined_at:%d %b %Y})",
            inline=False,
        )

    if profile and profile["favorite_genre"]:
        embed.add_field(name="Favorite genre", value=escape_markdown(profile["favorite_genre"]), inline=True)
    if profile and profile["goodreads"]:
        label, url = goodreads_link(profile["goodreads"])
        embed.add_field(name="Goodreads", value=f"[{escape_markdown(label)}]({url})", inline=True)
    if profile and profile["storygraph"]:
        label, url = storygraph_link(profile["storygraph"])
        embed.add_field(name="StoryGraph", value=f"[{escape_markdown(label)}]({url})", inline=True)

    if favorites:
        lines = []
        for row in favorites:
            author = f" — {escape_markdown(row['authors'])}" if row["authors"] else ""
            lines.append(f"{row['slot']}. {escape_markdown(trim(row['title'], 80))}{author}")
        embed.add_field(name="Top 5 favorites", value="\n".join(lines), inline=False)

    embed.add_field(name="Reading stats", value=_stats_text(stats), inline=False)
    return embed


def has_profile_details(profile: aiosqlite.Row | None, favorites: list[aiosqlite.Row]) -> bool:
    has_fields = bool(profile and (profile["favorite_genre"] or profile["goodreads"] or profile["storygraph"]))
    return has_fields or bool(favorites)


def _stats_text(stats: UserStats) -> str:
    if not stats.total_finished and not stats.highest:
        return "No finished books yet."
    lines = []
    if stats.highest and stats.lowest:
        lines.append(
            f"Highest rated: {escape_markdown(trim(stats.highest.title, 60))} ({format_rating(stats.highest.units)})"
        )
        lines.append(
            f"Lowest rated: {escape_markdown(trim(stats.lowest.title, 60))} ({format_rating(stats.lowest.units)})"
        )
    lines.append(f"Finished: {stats.finished_this_year} this year, {stats.finished_this_month} this month")
    if stats.average_units is not None:
        lines.append(f"Average rating given: {format_rating(stats.average_units)}")
    share = stats.club_share
    if share is not None:
        lines.append(f"Club books finished: {stats.club_finished} ({share:.0f}% of finished books)")
    return "\n".join(lines)
