from cerlen.books.isbn import clean, to_isbn13


def test_isbn10_converts_and_bad_rejected():
    assert to_isbn13(clean("0-306-40615-2")) == "9780306406157"
    assert to_isbn13("9780306406157") == "9780306406157"
    assert to_isbn13("1234567890") is None
