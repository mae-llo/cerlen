import pytest

from cerlen.ratings import InvalidRating, format_rating, to_units


def test_quarter_steps_round_trip():
    assert to_units(1) == 4
    assert to_units(4.25) == 17
    assert to_units(5) == 20
    assert format_rating(17) == "4.25"
    assert format_rating(18) == "4.5"
    assert format_rating(4) == "1"


@pytest.mark.parametrize("bad", [0, 0.75, 4.1, 5.25, -1])
def test_rejects_bad_ratings(bad):
    with pytest.raises(InvalidRating):
        to_units(bad)
