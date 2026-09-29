import json
import structlog
import redis
from typing import Optional

from app.config import (
    REDIS_URL,
    MEMORY_TTL_SECONDS,
    MAX_RECENT_TOPICS,
)
from app.schemas import MemoryEntry

logger = structlog.get_logger()

# Single shared Redis client for the app
redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
)

RECENT_TOPICS_KEY = "memory:recent"


def _topic_key(topic: str) -> str:
    return f"memory:topic:{topic}"


def save_memory(topic: str, report: str) -> bool:
    """
    Save a research report for a topic.
    Returns True on success, False on failure.
    """
    try:
        entry = MemoryEntry(topic=topic, report=report)

        pipe = redis_client.pipeline()
        pipe.set(_topic_key(topic), entry.model_dump_json(), ex=MEMORY_TTL_SECONDS)
        pipe.lpush(RECENT_TOPICS_KEY, topic)
        pipe.ltrim(RECENT_TOPICS_KEY, 0, MAX_RECENT_TOPICS - 1)
        pipe.execute()

        logger.info("memory_saved", topic=topic, ttl=MEMORY_TTL_SECONDS)
        return True

    except Exception as e:
        logger.error("memory_save_failed", topic=topic, error=str(e))
        return False


def get_memory(topic: str) -> Optional[MemoryEntry]:
    """
    Fetch a previously saved report for a topic.
    Returns None if not found or on error.
    """
    try:
        raw = redis_client.get(_topic_key(topic))
        if not raw:
            logger.info("memory_miss", topic=topic)
            return None

        entry = MemoryEntry.model_validate_json(raw)
        logger.info("memory_hit", topic=topic)
        return entry

    except Exception as e:
        logger.error("memory_get_failed", topic=topic, error=str(e))
        return None


def get_recent_topics(limit: int = 10) -> list[str]:
    """Return the most recently researched topics."""
    try:
        return redis_client.lrange(RECENT_TOPICS_KEY, 0, limit - 1)
    except Exception as e:
        logger.error("memory_recent_failed", error=str(e))
        return []


def get_last_memory() -> Optional[MemoryEntry]:
    """Return the most recent memory entry, or None."""
    recent = get_recent_topics(limit=1)
    if not recent:
        return None
    return get_memory(recent[0])


def clear_memory() -> int:
    """Delete all memory entries. Returns the count of deleted keys."""
    try:
        keys = redis_client.keys("memory:topic:*")
        if keys:
            redis_client.delete(*keys)
        redis_client.delete(RECENT_TOPICS_KEY)
        logger.info("memory_cleared", count=len(keys))
        return len(keys)
    except Exception as e:
        logger.error("memory_clear_failed", error=str(e))
        return 0