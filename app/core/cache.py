"""
Redis caching service for high-performance data access.

VERSION 1.0 - AGGRESSIVE CACHING STRATEGY

This module provides a centralized Redis caching layer to dramatically improve
backend performance by caching frequently accessed data.

Performance Targets:
- /api/reports/summary: 5-15s → 50-100ms (150x faster)
- /api/client-accounts/stats: 3s → 100ms (30x faster)
- /api/simulation/executed-dates: 1s → 0ms (instant)

Cache Strategy:
- Short TTL (30-60s) for frequently changing data like summary stats
- Medium TTL (5-15 min) for semi-static data like simulation dates
- Invalidation on data mutations (POST/PUT/DELETE operations)

Usage:
    from app.core.cache import cache_service

    # Get cached data
    data = await cache_service.get("my_key")

    # Set cached data with TTL
    await cache_service.set("my_key", {"data": "value"}, ttl=60)

    # Delete cached data
    await cache_service.delete("my_key")
"""

import json
import logging
from typing import Any, Optional
from redis import Redis
from redis.exceptions import RedisError
import os

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis-based caching service for high-performance data access.

    Implements connection pooling, automatic serialization, and error handling.
    """

    def __init__(self):
        """Initialize Redis connection with connection pooling."""
        self.redis_client: Optional[Redis] = None
        self.enabled = False

    def connect(self) -> None:
        """
        Establish connection to Redis server.

        Falls back gracefully if Redis is not available (cache disabled mode).
        """
        try:
            # Get Redis configuration from environment
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_db = int(os.getenv("REDIS_DB", "0"))
            redis_password = os.getenv("REDIS_PASSWORD", None)

            # Create Redis connection with connection pooling
            self.redis_client = Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True,  # Auto-decode bytes to strings
                socket_connect_timeout=5,
                socket_timeout=5,
                max_connections=50,  # Connection pool size
            )

            # Test connection
            self.redis_client.ping()
            self.enabled = True
            logger.info(f"✓ Redis cache connected successfully to {redis_host}:{redis_port}")

        except RedisError as e:
            logger.warning(f"⚠ Redis unavailable, running without cache: {e}")
            self.enabled = False
            self.redis_client = None

        except Exception as e:
            logger.error(f"✗ Failed to initialize Redis cache: {e}")
            self.enabled = False
            self.redis_client = None

    def disconnect(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Redis cache connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            finally:
                self.redis_client = None
                self.enabled = False

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve cached data by key.

        Args:
            key: Cache key to retrieve

        Returns:
            Deserialized cached data if found, None otherwise
        """
        if not self.enabled or not self.redis_client:
            return None

        try:
            cached_value = self.redis_client.get(key)
            if cached_value:
                logger.debug(f"✓ Cache HIT: {key}")
                return json.loads(cached_value)

            logger.debug(f"✗ Cache MISS: {key}")
            return None

        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Cache get error for key '{key}': {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> bool:
        """
        Store data in cache with TTL.

        Args:
            key: Cache key
            value: Data to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (default: 60s)

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            serialized_value = json.dumps(value, default=str)  # default=str for datetime
            self.redis_client.setex(key, ttl, serialized_value)
            logger.debug(f"✓ Cache SET: {key} (TTL: {ttl}s)")
            return True

        except (RedisError, TypeError, ValueError) as e:
            logger.warning(f"Cache set error for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete cached data by key.

        Args:
            key: Cache key to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            deleted_count = self.redis_client.delete(key)
            if deleted_count > 0:
                logger.debug(f"✓ Cache DELETE: {key}")
                return True
            return False

        except RedisError as e:
            logger.warning(f"Cache delete error for key '{key}': {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "summary:*")

        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self.redis_client:
            return 0

        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted_count = self.redis_client.delete(*keys)
                logger.debug(f"✓ Cache DELETE PATTERN: {pattern} ({deleted_count} keys)")
                return deleted_count
            return 0

        except RedisError as e:
            logger.warning(f"Cache delete pattern error for '{pattern}': {e}")
            return 0

    async def clear_all(self) -> bool:
        """
        Clear entire cache database.

        WARNING: Use with caution in production!

        Returns:
            True if cleared successfully, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            self.redis_client.flushdb()
            logger.info("✓ Cache CLEARED (entire database)")
            return True

        except RedisError as e:
            logger.error(f"Cache clear error: {e}")
            return False

    def is_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self.enabled


# Global cache service instance
cache_service = CacheService()
