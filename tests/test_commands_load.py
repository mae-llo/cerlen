"""Builds the bot's command tree without connecting to Discord."""

import pytest

from cerlen.bot import EXTENSIONS, CerlenBot
from cerlen.settings import Settings
from cerlen.views import dynamic_items


@pytest.fixture
async def bot(tmp_path):
    settings = Settings(token="x", guild_id=1, data_dir=tmp_path, contact="", log_level="INFO")
    instance = CerlenBot(settings)
    yield instance
    # The reminder loop starts when the cog loads; stop it so the test can end.
    for name in list(instance.cogs):
        await instance.remove_cog(name)


async def test_all_cogs_load_and_every_group_exists(bot):
    for extension in EXTENSIONS:
        await bot.load_extension(extension)
    top = {c.name: c for c in bot.tree.get_commands()}
    assert set(top) == {
        "book", "club", "queue", "progress", "review", "stats", "profile",
        "tbr", "reading", "log", "config", "data", "help",
    }

    def subs(name):
        return {c.name for c in top[name].commands}

    assert subs("club") == {"start", "current", "join", "leave", "history", "deadline", "reminders", "finish", "cancel"}
    assert subs("queue") == {"add", "list", "remove", "move", "poll", "poll-close", "random", "next", "choose"}
    assert subs("progress") == {"update", "finished", "dnf"}
    assert subs("review") == {"add", "edit", "delete", "remove"}
    assert subs("tbr") == {"add", "list", "remove", "move"}
    assert subs("reading") == {"start", "list", "pause", "resume", "remove"}
    assert subs("log") == {"add", "list", "delete"}
    assert subs("data") == {"export", "delete"}
    assert {"goodreads", "storygraph", "genre", "favorites", "show", "reminder-time"} <= subs("config")


def test_button_templates_are_unique():
    patterns = [item.__discord_ui_compiled_template__.pattern for item in dynamic_items()]
    assert all(p.startswith("cerlen:") for p in patterns)
    assert len(set(patterns)) == len(patterns)
