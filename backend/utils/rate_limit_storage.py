import time
import redis
import logging
from typing import Dict, Optional, Tuple
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from config.settings import settings

from config.redis_cache import cache as global_cache

logger = logging.getLogger(__name__)

class RateLimitStorage(ABC):
    """
    Abstract base for rate limit storage.

    Why abstract? This lets us swap storage backends (Redis, in-memory, database)
    without changing the rate limiting logic.
    """

    @abstractmethod
    def increment_and_check(self, key: str, window_seconds: int, limit: int) -> Tuple[int, bool]:
        """
        Increment counter and check if limit exceeded.
        
        Returns: (current_count, is_allowed)
        """
        pass

    @abstractmethod
    def get_reset_time(self, key: str, window_seconds: int) -> int:
        """
        Get when the rate limit window resets (Unix timestamp)
        """
        pass

class RedisRateLimitStorage(RateLimitStorage):
    """
    Redis-based rate limiting using sliding window algorithm.
    
    Why Redis? It's atomic, distributed, and persistent across container restarts.
    Why sliding window? More accurate than fixed windows, prevents thundering herd.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or getattr(global_cache, "client", None)
        if self.redis_client:
            logger.info("🔗 Using shared Redis client for rate limiting")
            try:
                self.redis_client.ping()
            except Exception as e:
                logger.info(f"⚠️ Shared Redis client unavailable for rate limiting: {e}")
                self.redis_client = None
                
        if not self.redis_client:
            try:
                self.redis_client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    socket_timeout=1,
                    socket_connect_timeout=1,
                    retry_on_timeout=True     
                )
                # Test connection
                self.redis_client.ping()
                logger.info("✅ Redis rate limit storage connected")
            except Exception as e:
                logger.info(f"⚠️ Redis unavailable for rate limiting: {e}")
                self.redis_client = None

    def increment_and_check(self, key: str, window_seconds: int, limit: int) -> Tuple[int, bool]:
        """
        Sliding window rate limiting with Redis.

        Algorithm:
        1. Remove expired entries (older than window)
        2. Count current entries in window
        3. If under limit, add new entry
        4. Return count and whether request is allowed
        """

        if not self.redis_client:
            return 0, True  # Allow all if Redis is down
        
        try:
            current_time = time.time()
            window_start = current_time - window_seconds

            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()

            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current entries
            pipe.zcard(key)

            # Execute pipeline
            results = pipe.execute()
            current_count = results[1]

            # Check if we're under the limit
            if current_count < limit:
                # Add new entry with current timestamp as score
                self.redis_client.zadd(key, {str(current_time): current_time})
                # Set TTL to prevent memory leaks
                self.redis_client.expire(key, window_seconds + 60)
                return current_count + 1, True
            else:
                return current_count, False
            
        except Exception as e:
            logger.error(f"Redis rate limit error for key {key}: {e}")
            return 0, True  # Fail open on errors
        
    def get_reset_time(self, key: str, window_seconds: int) -> int:
        """
        Get when the oldest entry in the window expires
        """
        if not self.redis_client:
            return int(time.time() + window_seconds)
        
        try:
            # Get oldest entry
            oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_time = oldest[0][1]
                return int(oldest_time + window_seconds)
            else:
                return int(time.time() + window_seconds)
        except Exception as e:
            logger.error(f"Redis reset time error for key {key}: {e}")
            return int(time.time() + window_seconds)

class InMemoryRateLimitStorage(RateLimitStorage):
    """
    In-memory fallback storage.
    
    Why fallback? If Redis is down, we still want basic rate limiting
    rather than no protection at all.
    """

    def __init__(self):
        self.storage: Dict[str, deque] = defaultdict(deque)
        logger.info("📝 Using in-memory rate limit storage (fallback mode)")

    def increment_and_check(self, key: str, window_seconds: int, limit: int) -> Tuple[int, bool]:
        current_time = time.time()
        window_start = current_time - window_seconds

        # Clean expired entries
        queue = self.storage[key]
        while queue and queue[0] < window_start:
            queue.popleft()

        # Check limit
        if len(queue) < limit:
            queue.append(current_time)
            return len(queue), True
        else:
            return len(queue), False
        
    def get_reset_time(self, key: str, window_seconds: int) -> int:
        queue = self.storage[key]
        if queue:
            return int(queue[0] + window_seconds)
        return int(time.time() + window_seconds)
    
# Storage factory
def create_rate_limit_storage() -> RateLimitStorage:
    """
    Create the appropriate storage 
    
    Why factory? Clean way to handle Redis availability and fallbacks.
    """
    redis_storage = RedisRateLimitStorage()
    if redis_storage.redis_client:
        return redis_storage
    else:
        logger.warning("🔄 Falling back to in-memory rate limiting")
        return InMemoryRateLimitStorage()