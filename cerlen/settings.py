"""Settings come from environment variables (or a .env file), never from code."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    token: str
    guild_id: int
    data_dir: Path
    contact: str
    log_level: str

    @property
    def database_path(self) -> Path:
        return self.data_dir / "cerlen.db"

    @property
    def voice_path(self) -> Path:
        return self.data_dir / "voice.json"


def load_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")

    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")

    raw_guild = os.environ.get("GUILD_ID", "").strip()
    if not raw_guild.isdigit():
        raise SystemExit("GUILD_ID must be your server's numeric ID. See .env.example.")

    data_dir = Path(os.environ.get("DATA_DIR", "data")).expanduser()
    if not data_dir.is_absolute():
        data_dir = BASE_DIR / data_dir

    return Settings(
        token=token,
        guild_id=int(raw_guild),
        data_dir=data_dir,
        contact=os.environ.get("CONTACT", "").strip(),
        log_level=os.environ.get("LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )
