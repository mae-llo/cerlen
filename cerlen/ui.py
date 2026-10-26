"""Small reusable pieces of interface."""

from __future__ import annotations

import discord


class ConfirmView(discord.ui.View):
    """Yes/No buttons shown only to the person who ran the command."""

    def __init__(self, user_id: int, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.confirmed: bool | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        await interaction.response.edit_message(view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        await interaction.response.edit_message(view=None)
        self.stop()


async def confirm(interaction: discord.Interaction, text: str) -> bool:
    """Ask privately; True only if the person pressed Confirm."""
    view = ConfirmView(interaction.user.id)
    await interaction.response.send_message(text, view=view, ephemeral=True)
    await view.wait()
    return bool(view.confirmed)
