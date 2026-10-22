"""Extra lines for the /config, /book and /help commands.

Importing this module adds them to the defaults in voice_defaults.py, so they
can be overridden in data/voice.json like any other line.
"""

from __future__ import annotations

from cerlen.voice_defaults import DEFAULTS

EXTRA: dict[str, str] = {
    "setting_saved": "That setting has been saved.",
    "invalid_time": "Enter the time as HH:MM on a 24-hour clock, for example 09:00.",
    "invalid_timezone": "I do not recognise that timezone. Use a name such as America/New_York.",
    "invalid_days": "Enter the reminder days as numbers from 0 to 60, separated by commas, for example 7,3,1,0.",
    "wrong_channel_type": "That channel is not the right kind. Choose a forum channel or a text channel.",
    "no_permission": "I do not have permission to post in {channel}. Please check my channel permissions.",
    "book_lookup_failed": "I could not reach the book databases just now. Please try again shortly.",
    "button_not_yours": "That is not available to you.",
    "help_footer": "Commands marked (admin) are restricted to the admins.",
}

DEFAULTS.update({key: value for key, value in EXTRA.items() if key not in DEFAULTS})
