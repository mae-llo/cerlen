"""A thin async wrapper around one SQLite connection, with numbered migrations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import aiosqlite

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


@dataclass(frozen=True)
class Result:
    lastrowid: int | None
    rowcount: int


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected.")
        return self._conn

    async def connect(self) -> None:
        in_memory = self.path == ":memory:"
        if not in_memory:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        if not in_memory:
            await self._conn.execute("PRAGMA journal_mode = WAL")
        await self._migrate()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> Result:
        cursor = await self.conn.execute(sql, params)
        await self.conn.commit()
        result = Result(cursor.lastrowid, cursor.rowcount)
        await cursor.close()
        return result

    async def batch(self, statements: Iterable[tuple[str, Sequence[Any]]]) -> None:
        """Run several statements as one all-or-nothing change."""
        try:
            for sql, params in statements:
                await self.conn.execute(sql, params)
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    async def fetchone(self, sql: str, params: Sequence[Any] = ()) -> aiosqlite.Row | None:
        async with self.conn.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[aiosqlite.Row]:
        async with self.conn.execute(sql, params) as cursor:
            return list(await cursor.fetchall())

    async def _migrate(self) -> None:
        row = await self.fetchone("PRAGMA user_version")
        current = int(row[0]) if row else 0
        files = sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda p: int(p.stem.split("_")[0]))
        for path in files:
            number = int(path.stem.split("_")[0])
            if number <= current:
                continue
            log.info("Applying migration %s", path.name)
            await self.conn.executescript(path.read_text(encoding="utf-8"))
            await self.conn.execute(f"PRAGMA user_version = {number}")
            await self.conn.commit()
