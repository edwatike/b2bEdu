"""
Redis Cache Service для B2B Platform
"""
import json
import logging
from typing import Optional, Any
from datetime import timedelta
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisCache:
    """Async Redis cache service"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self._client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._client.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Cache disabled.")
            self._client = None
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self._client:
            await self._client.close()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self._client:
            return None
        
        try:
            value = await self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 300):
        """Set value in cache with TTL (seconds)"""
        if not self._client:
            return False
        
        try:
            await self._client.setex(
                key,
                ttl,
                json.dumps(value, default=str)
            )
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str):
        """Delete key from cache"""
        if not self._client:
            return False
        
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def clear_pattern(self, pattern: str):
        """Clear all keys matching pattern"""
        if not self._client:
            return False
        
        try:
            keys = await self._client.keys(pattern)
            if keys:
                await self._client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Redis clear pattern error: {e}")
            return False


# Singleton instance
_cache_instance: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """Get cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance


# Cache TTL constants
CACHE_TTL_CHECKO = 86400  # 24 hours
CACHE_TTL_SUPPLIERS = 300  # 5 minutes
CACHE_TTL_BLACKLIST = 600  # 10 minutes
CACHE_TTL_KEYWORDS = 300  # 5 minutes
