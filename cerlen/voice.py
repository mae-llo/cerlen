"""Cerlen's lines.

Every message the bot sends on its own goes through Voice.say(key, ...).
Plain defaults live in voice_defaults.py. Your own lines go in data/voice.json:

    {
      "welcome": "Welcome to the archives, {user}.",
      "tbr_added": ["{user} has shelved {title}.", "{title} joins {user}'s shelf."]
    }

A list means several versions; one is picked at random each time.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path

from cerlen.voice_defaults import DEFAULTS

log = logging.getLogger(__name__)


class _Safe(dict):
    """Leave unknown {placeholders} as written instead of failing."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class Voice:
    def __init__(self, overrides_path: Path | None = None):
        self.overrides_path = overrides_path
        self.overrides: dict[str, list[str]] = {}
        self.reload()

    def reload(self) -> None:
        self.overrides = {}
        path = self.overrides_path
        if path is None or not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            log.warning("Could not read %s (%s); using default lines.", path, error)
            return
        if not isinstance(raw, dict):
            log.warning("%s must hold a JSON object; using default lines.", path)
            return
        for key, value in raw.items():
            options = [value] if isinstance(value, str) else value
            if isinstance(options, list):
                lines = [line for line in options if isinstance(line, str) and line.strip()]
                if lines:
                    self.overrides[key] = lines
            if key not in DEFAULTS:
                log.warning("voice.json has an unknown line %r; it will never be used.", key)

    def say(self, key: str, **values: object) -> str:
        default = DEFAULTS[key]
        lines = self.overrides.get(key) or [default]
        safe = _Safe({name: str(value) for name, value in values.items()})
        try:
            return random.choice(lines).format_map(safe)
        except (ValueError, IndexError, KeyError, AttributeError):
            # A stray brace in a typed line should never break a command.
            log.warning("Line %r could not be formatted; using the default.", key)
            return default.format_map(safe)
