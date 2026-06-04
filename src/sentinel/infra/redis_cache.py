from __future__ import annotations

import asyncio
import hashlib
import json
import os
from typing import Any

try:
    from redis.asyncio import ConnectionPool, Redis
except ModuleNotFoundError:  # pragma: no cover - exercised in lightweight test envs
    ConnectionPool = None  # type: ignore[assignment]
    Redis = None  # type: ignore[assignment]


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


import sqlite3
import time
from pathlib import Path


class InMemoryRedis:
    """SQLite-backed shared multiprocess KV/Queue store for local zero-dependency runs."""

    # Anchor the db to the project root (4 levels up from sentinel/infra/redis_cache.py)
    # so the path is identical regardless of which directory each process was launched from.
    _DB_PATH: str = str(Path(__file__).resolve().parent.parent.parent.parent / "redis_fallback.db")

    def __init__(self) -> None:
        import logging

        self.logger = logging.getLogger("InMemoryRedis")
        self.db_path = self._DB_PATH
        self.logger.info("Initializing SQLite InMemoryRedis at %s", self.db_path)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS kv (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        expire_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT,
                        value TEXT
                    )
                """)
        except Exception as e:
            self.logger.exception("Failed to initialize SQLite database: %s", e)
        finally:
            conn.close()

    async def incr(self, key: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                cursor = conn.execute(
                    "SELECT value FROM kv WHERE key = ? AND (expire_at IS NULL OR expire_at > ?)",
                    (key, time.time()),
                )
                row = cursor.fetchone()
                new_val = int(row[0]) + 1 if row else 1
                conn.execute(
                    "INSERT OR REPLACE INTO kv (key, value, expire_at) VALUES (?, ?, ?)",
                    (key, str(new_val), None),
                )
                return new_val
        except Exception as e:
            self.logger.exception("Error in incr for key %s: %s", key, e)
            return 1
        finally:
            conn.close()

    async def expire(self, key: str, seconds: int) -> bool:
        expire_at = time.time() + seconds
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                cursor = conn.execute("SELECT value FROM kv WHERE key = ?", (key,))
                if cursor.fetchone():
                    conn.execute("UPDATE kv SET expire_at = ? WHERE key = ?", (expire_at, key))
                    return True
                return False
        except Exception as e:
            self.logger.exception("Error in expire for key %s: %s", key, e)
            return False
        finally:
            conn.close()

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        expire_at = (time.time() + ex) if ex is not None else None
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                if nx:
                    cursor = conn.execute(
                        "SELECT 1 FROM kv WHERE key = ? AND (expire_at IS NULL OR expire_at > ?)",
                        (key, time.time()),
                    )
                    if cursor.fetchone() is not None:
                        return False
                conn.execute(
                    "INSERT OR REPLACE INTO kv (key, value, expire_at) VALUES (?, ?, ?)",
                    (key, value, expire_at),
                )
                return True
        except Exception as e:
            self.logger.exception("Error in set for key %s: %s", key, e)
            return False
        finally:
            conn.close()

    async def get(self, key: str) -> str | None:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT value FROM kv WHERE key = ? AND (expire_at IS NULL OR expire_at > ?)",
                (key, time.time()),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            self.logger.exception("Error in get for key %s: %s", key, e)
            return None
        finally:
            conn.close()

    async def exists(self, key: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT 1 FROM kv WHERE key = ? AND (expire_at IS NULL OR expire_at > ?)",
                (key, time.time()),
            )
            return 1 if cursor.fetchone() else 0
        except Exception as e:
            self.logger.exception("Error in exists for key %s: %s", key, e)
            return 0
        finally:
            conn.close()

    async def ttl(self, key: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT expire_at FROM kv WHERE key = ? AND (expire_at IS NULL OR expire_at > ?)",
                (key, time.time()),
            )
            row = cursor.fetchone()
            if not row:
                return -2
            if row[0] is None:
                return -1
            return max(0, int(row[0] - time.time()))
        except Exception as e:
            self.logger.exception("Error in ttl for key %s: %s", key, e)
            return -2
        finally:
            conn.close()

    async def rpush(self, key: str, value: str) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("INSERT INTO queue (key, value) VALUES (?, ?)", (key, value))
        except Exception as e:
            self.logger.exception("Error in rpush for key %s: %s", key, e)
        finally:
            conn.close()

    async def blpop(self, key: str, timeout: int = 1) -> tuple[str, str] | None:
        end_time = time.time() + timeout
        while time.time() < end_time:
            conn = sqlite3.connect(self.db_path)
            try:
                with conn:
                    cursor = conn.execute(
                        "SELECT id, value FROM queue WHERE key = ? ORDER BY id ASC LIMIT 1", (key,)
                    )
                    row = cursor.fetchone()
                    if row:
                        row_id, value = row
                        conn.execute("DELETE FROM queue WHERE id = ?", (row_id,))
                        return (key, value)
            except Exception as e:
                self.logger.exception("Error in blpop for key %s: %s", key, e)
            finally:
                conn.close()
            await asyncio.sleep(0.1)
        return None


if ConnectionPool is not None and Redis is not None:
    pool = ConnectionPool.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2.0,
        socket_timeout=2.0,
        max_connections=100,
        retry_on_timeout=True,
    )
    redis_client: Any = Redis(connection_pool=pool)
else:
    redis_client = InMemoryRedis()


class CacheManager:
    """
    Handles low-latency caching, bridge heartbeats, and onboarding commands.
    """

    def __init__(self, client: Redis) -> None:
        self.r = client
        self.risk_score_ttl = 60
        self.heartbeat_ttl = 60
        self.onboarding_queue = "sentinel:onboarding:queue"

    async def ping(self) -> bool:
        try:
            await self.r.ping()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self.r.aclose()

    def build_risk_cache_key(self, user_id: str, payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"risk:{user_id}:{fingerprint}"

    def build_behavioral_profile_key(self, user_id: str) -> str:
        return f"profile:{user_id}:behavioral"

    def build_intervention_lock_key(self, ticket_id: int) -> str:
        return f"intervention:{ticket_id}"

    def build_retraining_lock_key(self, user_id: str) -> str:
        return f"retrain:{user_id}"

    async def cache_risk_score(self, key: str, assessment: dict[str, Any]) -> None:
        await self.r.set(key, json.dumps(assessment), ex=self.risk_score_ttl)

    async def get_cached_risk(self, key: str) -> dict[str, Any] | None:
        raw = await self.r.get(key)
        return json.loads(raw) if raw else None

    async def cache_behavioral_profile(self, user_id: str, profile: dict[str, Any]) -> None:
        await self.r.set(
            self.build_behavioral_profile_key(user_id),
            json.dumps(profile, sort_keys=True),
            ex=300,
        )

    async def get_behavioral_profile(self, user_id: str) -> dict[str, Any] | None:
        raw = await self.r.get(self.build_behavioral_profile_key(user_id))
        return json.loads(raw) if raw else None

    async def acquire_intervention_lock(self, ticket_id: int, ttl_seconds: int = 10) -> bool:
        return bool(
            await self.r.set(
                self.build_intervention_lock_key(ticket_id),
                "locked",
                ex=ttl_seconds,
                nx=True,
            )
        )

    async def acquire_retraining_lock(self, user_id: str, ttl_seconds: int = 300) -> bool:
        return bool(
            await self.r.set(
                self.build_retraining_lock_key(user_id),
                "locked",
                ex=ttl_seconds,
                nx=True,
            )
        )

    async def set_heartbeat(self, user_id: str) -> bool:
        ttl = await self.r.ttl(f"presence:{user_id}")
        if ttl is None or ttl < self.heartbeat_ttl - 5:
            return bool(await self.r.set(f"presence:{user_id}", "active", ex=self.heartbeat_ttl))
        return True

    async def ping_state(self, user_id: str) -> bool:
        return bool(await self.r.exists(f"presence:{user_id}"))

    async def enqueue_onboarding_job(self, payload: dict[str, Any]) -> None:
        await self.r.rpush(self.onboarding_queue, json.dumps(payload))

    async def dequeue_onboarding_job(self, timeout_seconds: int = 1) -> dict[str, Any] | None:
        item = await self.r.blpop(self.onboarding_queue, timeout=timeout_seconds)
        if item is None:
            return None
        _, raw = item
        return json.loads(raw)


async def get_redis() -> Redis:
    return redis_client


cache_manager = CacheManager(redis_client)
