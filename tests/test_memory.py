"""
Tests for app.memory — save/get/recent/clear against Redis.

Uses a dedicated test key namespace so it doesn't collide with real data.
Requires Redis running on localhost:6379.
"""
import pytest

from app.memory import (
    save_memory,
    get_memory,
    get_recent_topics,
    get_last_memory,
    clear_memory,
    redis_client,
)
from app.schemas import MemoryEntry


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(autouse=True)
def clean_redis():
    """Clear memory keys before and after each test."""
    clear_memory()
    yield
    clear_memory()


@pytest.fixture
def redis_available():
    """Skip the test if Redis is not reachable."""
    try:
        redis_client.ping()
    except Exception:
        pytest.skip("Redis not available")


# ============================================================
# save + get
# ============================================================

def test_save_and_get_memory(redis_available):
    ok = save_memory("test topic", "This is a test report.")
    assert ok is True

    entry = get_memory("test topic")
    assert entry is not None
    assert isinstance(entry, MemoryEntry)
    assert entry.topic == "test topic"
    assert entry.report == "This is a test report."
    assert entry.timestamp is not None


def test_get_missing_topic_returns_none(redis_available):
    entry = get_memory("never researched topic")
    assert entry is None


def test_save_overwrites_existing(redis_available):
    save_memory("topic", "first report")
    save_memory("topic", "second report")

    entry = get_memory("topic")
    assert entry.report == "second report"


# ============================================================
# Recent topics
# ============================================================

def test_recent_topics_lists_saved_topics(redis_available):
    save_memory("topic one", "r1")
    save_memory("topic two", "r2")
    save_memory("topic three", "r3")

    recent = get_recent_topics(limit=10)
    assert "topic three" in recent
    assert "topic two" in recent
    assert "topic one" in recent


def test_recent_topics_order_is_newest_first(redis_available):
    save_memory("first", "r1")
    save_memory("second", "r2")

    recent = get_recent_topics(limit=10)
    assert recent[0] == "second"
    assert recent[1] == "first"


def test_get_last_memory(redis_available):
    save_memory("first", "r1")
    save_memory("last", "r2")

    last = get_last_memory()
    assert last is not None
    assert last.topic == "last"
    assert last.report == "r2"


def test_get_last_memory_when_empty(redis_available):
    last = get_last_memory()
    assert last is None


# ============================================================
# Clear
# ============================================================

def test_clear_memory_removes_all_topics(redis_available):
    save_memory("a", "r1")
    save_memory("b", "r2")

    cleared = clear_memory()
    assert cleared >= 2

    assert get_memory("a") is None
    assert get_memory("b") is None
    assert get_recent_topics() == []


def test_clear_memory_on_empty_returns_zero(redis_available):
    cleared = clear_memory()
    assert cleared == 0


# ============================================================
# Edge cases
# ============================================================

def test_save_memory_handles_empty_report(redis_available):
    ok = save_memory("topic", "")
    assert ok is True

    entry = get_memory("topic")
    assert entry is not None
    assert entry.report == ""


def test_recent_topics_limit(redis_available):
    for i in range(5):
        save_memory(f"topic{i}", f"report{i}")

    recent = get_recent_topics(limit=2)
    assert len(recent) == 2