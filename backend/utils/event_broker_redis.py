import asyncio
import json
from typing import AsyncGenerator, Optional
from redis import Redis as SyncRedis  # type: ignore
import redis as sync_redis_pkg  # used for sync fallback creation
import logging

logger = logging.getLogger(__name__)

import redis.asyncio as aioredis  # type: ignore
AsyncRedisType = aioredis.Redis

from config.redis_cache import cache as redis_cache  # existing RedisCache instance

from config.settings import settings
_configured_url = getattr(settings, "redis_url", None)

_redis: Optional[AsyncRedisType] = None
_redis_url: Optional[str] = None

async def init_redis(url: Optional[str] = None) -> None:
    """
    Initialize or reuse an async Redis client. Call at FastAPI startup.
    If the existing config.redis_cache.cache.client is already an async client, reuse it.
    Otherwise create a redis.asyncio.Redis client using the same URL.
    """
    global _redis, _redis_url
    url_to_use = url or _configured_url or getattr(redis_cache, "client", None) and getattr(redis_cache.client, "connection_pool", None) and None
    # prefer explicit url arg, then settings.redis_url
    _redis_url = url_to_use or _configured_url or "redis://localhost:6379/0"

    # if redis_cache has an async client instance, reuse it
    try:
        sync_client = getattr(redis_cache, "client", None)
        if aioredis is not None and sync_client is not None and isinstance(sync_client, aioredis.Redis):
            _redis = sync_client  # reuse existing async client
            await _redis.ping()
            logger.info("Reused async redis client from redis_cache")
            return
    except Exception:
        # ignore and create new async client
        logger.debug("Could not reuse redis_cache async client, creating new async client", exc_info=True)

    if aioredis is None:
        raise RuntimeError("redis.asyncio is not available; please install redis>=4.2 and use redis.asyncio")

    # create a dedicated async client (same URL)
    _redis = aioredis.from_url(_redis_url, decode_responses=True)
    await _redis.ping()
    logger.info("Initialized dedicated async redis client for event broker: %s", _redis_url)

def _ensure_redis_sync_client():
    """
    Return an existing sync client if available, otherwise create one from the configured URL.
    This is used for synchronous publish fallback.
    """
    # reuse existing sync client from redis_cache if present
    try:
        if redis_cache and getattr(redis_cache, "client", None):
            client = redis_cache.client
            if isinstance(client, SyncRedis):
                return client
    except Exception:
        pass

    # fallback: create a new sync client using same URL
    url = _redis_url or _configured_url or "redis://localhost:6379/0"
    return sync_redis_pkg.from_url(url, decode_responses=True)

async def _publish_async(request_id: str, event: dict) -> None:
    if _redis is None:
        raise RuntimeError("Async Redis client not initialized (init_redis not called)")
    channel = f"events:{request_id}"
    await _redis.publish(channel, json.dumps(event))

def publish_event(request_id: str, event: dict) -> None:
    """
    Publish an event. Safe to call from sync or async contexts.
    If called in an async context, schedule an async publish.
    If called in a sync/no-loop context, publish using a sync redis client in a thread.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # schedule the async publisher
        try:
            loop.create_task(_publish_async(request_id, event))
        except Exception:
            # if async client not initialized, fallback to sync publish in thread
            def _sync_pub_fallback():
                r = _ensure_redis_sync_client()
                try:
                    r.publish(f"events:{request_id}", json.dumps(event))
                except Exception:
                    logger.exception("Sync fallback publish failed")
            import threading
            threading.Thread(target=_sync_pub_fallback, daemon=True).start()
    else:
        # fallback: publish with a sync client in a background thread
        def _sync_pub():
            try:
                r = _ensure_redis_sync_client()
                r.publish(f"events:{request_id}", json.dumps(event))
            except Exception:
                logger.exception("Sync publish failed")
        import threading
        threading.Thread(target=_sync_pub, daemon=True).start()

async def subscribe_stream(request_id: str) -> AsyncGenerator[str, None]:
    """
    Async generator yielding raw JSON strings published to "events:{request_id}" channel.
    Use in SSE endpoint to stream messages to clients.
    """
    if _redis is None:
        raise RuntimeError("Async Redis client not initialized (init_redis not called)")
    channel = f"events:{request_id}"
    pubsub = _redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        # get_message supports timeout; we poll to allow client disconnect checks
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                await asyncio.sleep(0.05)
                continue
            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode()
            yield data
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception:
            pass