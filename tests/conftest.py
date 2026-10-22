import pytest_asyncio

from cerlen import repo
from cerlen.books.models import BookData
from cerlen.db import Database


@pytest_asyncio.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def book_ids(db):
    ids = []
    for n in range(1, 8):
        ids.append(await repo.upsert_book(db, BookData(title=f"Book {n}", authors="Author", isbn13=f"978000000000{n}")))
    return ids
