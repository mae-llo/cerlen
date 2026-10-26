"""Background loop: reminders and polls that close by themselves."""

from __future__ import annotations

import logging

from discord.ext import commands, tasks

from cerlen import flows

log = logging.getLogger(__name__)


class RemindersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop.start()

    async def cog_unload(self) -> None:
        self.loop.cancel()

    @tasks.loop(minutes=1)
    async def loop(self) -> None:
        try:
            await flows.process_reminders(self.bot)
        except Exception:  # one bad minute must not stop the loop
            log.exception("Reminder check failed")

    @loop.before_loop
    async def _wait_until_ready(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot) -> None:
    await bot.add_cog(RemindersCog(bot))
