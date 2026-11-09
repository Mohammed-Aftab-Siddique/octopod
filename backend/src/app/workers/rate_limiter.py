"""Durable Object backed rate limiter.

Workers isolates are ephemeral and not shared, so an in-memory dict cannot
enforce limits reliably. Each Durable Object uses its SQLite storage to keep
per-key hit timestamps across requests and isolates.
"""

import time

from workers import DurableObject

CREATE_TABLE = "CREATE TABLE IF NOT EXISTS hits (key TEXT NOT NULL, ts INTEGER NOT NULL)"
CREATE_INDEX = "CREATE INDEX IF NOT EXISTS ix_hits_key_ts ON hits (key, ts)"


class RateLimiter(DurableObject):
    def _ensure_schema(self) -> None:
        self.ctx.storage.sql.exec(CREATE_TABLE)
        self.ctx.storage.sql.exec(CREATE_INDEX)

    def _count(self, key: str, since: int) -> int:
        cursor = self.ctx.storage.sql.exec(
            "SELECT COUNT(*) AS count FROM hits WHERE key = ? AND ts > ?", key, since
        )
        row = cursor.one()
        try:
            return int(row["count"])
        except (KeyError, TypeError):
            return int(row[0])

    async def check(self, key: str, limit: int, window_seconds: int) -> bool:
        self._ensure_schema()
        now = int(time.time())
        since = now - int(window_seconds)
        self.ctx.storage.sql.exec("DELETE FROM hits WHERE ts <= ?", since)
        if self._count(key, since) >= int(limit):
            return False
        self.ctx.storage.sql.exec("INSERT INTO hits (key, ts) VALUES (?, ?)", key, now)
        return True
