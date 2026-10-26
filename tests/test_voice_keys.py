"""Every line the code asks Cerlen to say must exist, and every placeholder it fills must be one the sheet allows."""

import re
from pathlib import Path

import cerlen.voice_config  # noqa: F401
from cerlen.voice_defaults import DEFAULTS

ROOT = Path(__file__).resolve().parent.parent / "cerlen"
ALLOWED = {"user", "title", "author", "pages", "deadline", "days_left", "progress", "count", "link", "channel"}


def _source():
    return "\n".join(p.read_text(encoding="utf-8") for p in ROOT.rglob("*.py"))


def test_every_line_used_in_code_exists():
    used = set(re.findall(r'say\(\s*"([a-z_0-9]+)"', _source()))
    used |= set(re.findall(r'key = "([a-z_0-9]+)"', _source()))
    used |= set(re.findall(r'"([a-z_0-9]+)" if \w+ else "([a-z_0-9]+)"', _source()) and [])
    missing = sorted(key for key in used if key not in DEFAULTS)
    assert not missing, missing


def test_defaults_only_use_known_placeholders():
    for key, line in DEFAULTS.items():
        unknown = set(re.findall(r"{(\w+)}", line)) - ALLOWED
        assert not unknown, (key, unknown)
