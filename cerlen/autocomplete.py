"""Shared book autocomplete for every command that takes a book."""

from __future__ import annotations

import discord
from discord import app_commands


async def book_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    current = current.strip()
    if len(current) < 2 or interaction.client.books is None:
        return []
    try:
        suggestions = await interaction.client.books.suggest(current, limit=10)
    except Exception:  # autocomplete must never raise; Discord only has 3 seconds
        return []
    return [
        app_commands.Choice(name=s.label[:100], value=s.value[:100])
        for s in suggestions
    ]
