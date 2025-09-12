import redis
import json
import logging
from typing import Optional, Any, Dict
from config.settings import settings

logger = logging.getLogger(__name__)

class RedisCache:
    """
    Simple Redis wrapper with in-memory fallback.
    Backwards-compatible API:
      - set/get/delete
      - set_cache/get_cache/delete_cache
      - get_cached_query / set_cached_query
    """

    def __init__(self):
        logger.info("Initializing RedisCache")
        self.client: Optional[redis.Redis] = None
        self._store: Dict[str, Any] = {}
        self._connect()

    def _connect(self) -> None:
        """Try to connect to Redis; fall back to in-memory store on failure."""
        redis_url = getattr(settings, "redis_url", None)
        if not redis_url:
            logger.info("No redis_url configured, using in-memory cache")
            self.client = None
            return

        try:
            logger.info(f"Connecting to Redis at {redis_url}")
            client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5, socket_timeout=5)
            client.ping()
            self.client = client
            logger.info("✅ Redis connection established")
        except Exception as e:
            logger.info("❌ Redis connection failed, using in-memory cache: %s", e)
            self.client = None

    def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        try:
            payload = json.dumps(value, default=str)
            if self.client:
                logger.info('setting cache with redis client')
                self.client.setex(key, expire, payload)
            else:
                logger.info('setting cache with in-memory store')
                # in-memory store: ignore expire for simplicity
                self._store[key] = value
            return True
        except Exception as e:
            logger.error("Error setting cache key %s: %s", key, e)
            # fall back to in-memory
            try:
                self._store[key] = value
            except Exception:
                pass
            return False

    def get(self, key: str) -> Optional[Any]:
        try:
            if self.client:
                raw = self.client.get(key)
                if raw is None:
                    return None
                return json.loads(raw)
            return self._store.get(key)
        except Exception as e:
            logger.error("Error getting cache key %s: %s", key, e)
            return self._store.get(key)

    def delete(self, key: str) -> bool:
        try:
            if self.client:
                self.client.delete(key)
            else:
                self._store.pop(key, None)
            return True
        except Exception as e:
            logger.error("Error deleting cache key %s: %s", key, e)
            try:
                self._store.pop(key, None)
            except Exception:
                pass
            return False

# Global cache instance
cache = RedisCache()