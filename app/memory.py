import json
import redis
import os
import logging

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL)
MAX_MEMORY = 100


def save_memory(topic: str, report: str) -> None:
    """Save research result to memory."""
    memory = {"topic": topic, "report": report}
    redis_client.lpush("research_memory", json.dumps(memory))
    redis_client.ltrim("research_memory", 0, MAX_MEMORY - 1)
    logger.info(f"Saved to memory: {topic}")


def get_memory() -> list:
    """Get all research results."""
    items = redis_client.lrange("research_memory", 0, -1)
    return [json.loads(item) for item in items]


def get_last_memory() -> dict | None:
    """Get the most recent research result."""
    item = redis_client.lindex("research_memory", 0)
    return json.loads(item) if item else None


def clear_memory() -> None:
    """Clear all research history."""
    redis_client.delete("research_memory")
    logger.info("Memory cleared")