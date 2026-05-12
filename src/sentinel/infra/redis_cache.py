from __future__ import annotations

import hashlib
import json
import os
import asyncio
from typing import Any

try:
    from redis.asyncio import ConnectionPool, Redis
except ModuleNotFoundError:  # pragma: no cover - exercised in lightweight test envs
    ConnectionPool = None  # type: ignore[assignment]
    Redis = None  # type: ignore[assignment]


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class InMemoryRedis:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._values[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self._values.get(key)

    async def exists(self, key: str) -> int:
        return 1 if key in self._values else 0

    async def rpush(self, key: str, value: str) -> None:
        _ = key
        await self._queue.put(value)

    async def blpop(self, key: str, timeout: int = 1) -> tuple[str, str] | None:
        _ = key
        try:
            value = await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None
        return (key, value)


if ConnectionPool is not None and Redis is not None:
    pool = ConnectionPool.from_url(REDIS_URL, decode_responses=True)
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

    async def cache_risk_score(self, key: str, assessment: dict[str, Any]) -> None:
        await self.r.set(key, json.dumps(assessment), ex=self.risk_score_ttl)

    async def get_cached_risk(self, key: str) -> dict[str, Any] | None:
        raw = await self.r.get(key)
        return json.loads(raw) if raw else None

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
