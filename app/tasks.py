import structlog
from celery import Task

from app.celery_worker import celery
from app.memory import get_memory, save_memory
from app.config import TASK_MAX_RETRIES

logger = structlog.get_logger()


class ResearchTask(Task):
    """Base class with retry semantics for research tasks."""
    autoretry_for = (Exception,)
    max_retries = TASK_MAX_RETRIES
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    acks_late = True
    reject_on_worker_lost = True


@celery.task(base=ResearchTask, bind=True)
def run_research(self, topic: str) -> dict:
    """
    Run the research agent for a topic.
    Idempotent: returns cached result if the topic was already researched.
    """
    task_id = self.request.id
    logger.info("research_task_started", task_id=task_id, topic=topic)

    # ---- Idempotency: return cached result if available ----
    cached = get_memory(topic)
    if cached:
        logger.info("research_cache_hit", task_id=task_id, topic=topic)
        return {
            "topic": topic,
            "report": cached.report,
            "cached": True,
        }

    # ---- Progress: starting ----
    self.update_state(
        state="PROGRESS",
        meta={"stage": "initializing", "progress": 5},
    )

    # ---- Run the agent (imported lazily to avoid circular import) ----
    try:
        from app.agent import research_agent  # noqa: WPS433

        self.update_state(
            state="PROGRESS",
            meta={"stage": "researching", "progress": 20},
        )

        report = research_agent(topic)

    except Exception as e:
        logger.error("research_agent_failed", task_id=task_id, error=str(e))
        raise  # triggers autoretry

    # ---- Progress: saving ----
    self.update_state(
        state="PROGRESS",
        meta={"stage": "saving", "progress": 90},
    )

    try:
        save_memory(topic, report)
    except Exception as e:
        logger.warning("save_memory_failed", task_id=task_id, error=str(e))

    logger.info("research_task_completed", task_id=task_id, topic=topic)

    return {
        "topic": topic,
        "report": report,
        "cached": False,
    }