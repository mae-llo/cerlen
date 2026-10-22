import pytest

from cerlen.validation import (
    InvalidInput,
    clean_genre,
    clean_goodreads,
    clean_storygraph,
    goodreads_link,
    parse_days,
    parse_time,
    parse_timezone,
)


def test_goodreads_accepts_username_or_link():
    assert clean_goodreads(" reader_one ") == "reader_one"
    link = "https://www.goodreads.com/user/show/123-name"
    assert clean_goodreads(link) == link
    assert goodreads_link(link)[1] == link
    assert goodreads_link("reader_one")[1].endswith("/reader_one")


@pytest.mark.parametrize("bad", ["", "a", "has space", "http://goodreads.com/x", "https://evil.example/x"])
def test_goodreads_rejects(bad):
    with pytest.raises(InvalidInput):
        clean_goodreads(bad)


def test_storygraph_and_genre():
    assert clean_storygraph("page.turner") == "page.turner"
    with pytest.raises(InvalidInput):
        clean_storygraph("no spaces")
    assert clean_genre("  Science   Fiction ") == "Science Fiction"
    with pytest.raises(InvalidInput):
        clean_genre("<script>")


def test_time_timezone_days():
    assert parse_time("09:00") == "09:00"
    with pytest.raises(InvalidInput):
        parse_time("9am")
    assert parse_timezone("America/New_York") == "America/New_York"
    with pytest.raises(InvalidInput):
        parse_timezone("Not/AZone")
    assert parse_days("1, 7,3,7") == "7,3,1"
    with pytest.raises(InvalidInput):
        parse_days("100")
