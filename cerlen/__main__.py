"""Start the bot with:  python -m cerlen"""

from __future__ import annotations

import logging

from cerlen.bot import CerlenBot
from cerlen.settings import load_settings


def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    bot = CerlenBot(settings)
    bot.run(settings.token, log_handler=None)


if __name__ == "__main__":
    main()
