"""Builds the bot's command tree without connecting to Discord."""

import pytest

from cerlen.bot import EXTENSIONS, CerlenBot
from cerlen.settings import Settings


@pytest.fixture
def bot(tmp_path):
    settings = Settings(token="x", guild_id=1, data_dir=tmp_path, contact="", log_level="INFO")
    return CerlenBot(settings)


async def test_all_cogs_load_and_expected_commands_exist(bot):
    for extension in EXTENSIONS:
        await bot.load_extension(extension)
    names = {c.name for c in bot.tree.get_commands()}
    assert {"book", "profile", "config", "help"} <= names
    config = bot.tree.get_command("config")
    subs = {c.name for c in config.commands}
    assert {"goodreads", "storygraph", "genre", "favorites", "show", "reminder-time"} <= subs
    favorites = next(c for c in config.commands if c.name == "favorites")
    assert {c.name for c in favorites.commands} == {"add", "remove"}
