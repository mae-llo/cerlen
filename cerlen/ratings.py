"""Ratings are stored as whole quarter-stars: 4 (1 star) up to 20 (5 stars).

Storing integers avoids floating point rounding in averages and comparisons.
"""

from __future__ import annotations

from discord import app_commands

MIN_UNITS = 4
MAX_UNITS = 20
STEP = 0.25


class InvalidRating(ValueError):
    pass


def to_units(rating: float) -> int:
    """Convert 1..5 in quarter steps to whole units, or raise InvalidRating."""
    units = rating / STEP
    rounded = round(units)
    if abs(units - rounded) > 1e-9 or not (MIN_UNITS <= rounded <= MAX_UNITS):
        raise InvalidRating("Ratings run from 1 to 5 in quarter steps.")
    return int(rounded)


def from_units(units: float) -> float:
    return units * STEP


def format_rating(units: float) -> str:
    """4 -> '1', 17 -> '4.25', 18 -> '4.5'. Also used for averages of units."""
    text = f"{from_units(units):.2f}".rstrip("0").rstrip(".")
    return text or "0"


def rating_choices() -> list[app_commands.Choice[float]]:
    """The 17 allowed ratings as a fixed list, so a bad value cannot be typed."""
    return [
        app_commands.Choice(name=format_rating(units), value=from_units(units))
        for units in range(MIN_UNITS, MAX_UNITS + 1)
    ]
