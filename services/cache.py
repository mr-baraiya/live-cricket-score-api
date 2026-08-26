import time
import asyncio
from typing import Any, Dict, Optional, Tuple


class SimpleCache:
    def __init__(self, ttl: float = 10.0):
        self.ttl = ttl
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            timestamp, data = self._store[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self._store[key]
        return None

    def set(self, key: str, value: Any):
        self._store[key] = (time.time(), value)

    def clear(self):
        self._store.clear()

    def get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]


import os

cache_ttl_env = float(os.getenv("CACHE_TTL", "3.0"))
match_cache = SimpleCache(ttl=cache_ttl_env)
