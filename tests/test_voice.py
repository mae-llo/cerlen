import json

import cerlen.voice_config  # noqa: F401
from cerlen.voice import Voice
from cerlen.voice_defaults import DEFAULTS


def test_default_and_unknown_placeholder():
    voice = Voice(None)
    assert "{" not in voice.say("not_admin")
    assert voice.say("welcome", user="Ana").startswith("Welcome, Ana")


def test_overrides_and_bad_braces(tmp_path):
    path = tmp_path / "voice.json"
    path.write_text(json.dumps({"welcome": "Hello {user} {oops", "not_admin": ["No."]}), encoding="utf-8")
    voice = Voice(path)
    assert voice.say("not_admin") == "No."
    # A broken line falls back to the default instead of raising.
    assert voice.say("welcome", user="Ana").startswith("Welcome, Ana")


def test_unreadable_file_is_ignored(tmp_path):
    path = tmp_path / "voice.json"
    path.write_text("not json", encoding="utf-8")
    assert Voice(path).say("error") == DEFAULTS["error"]


def test_extra_lines_registered():
    assert "setting_saved" in DEFAULTS
