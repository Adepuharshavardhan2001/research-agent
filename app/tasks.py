import logging
from app.celery_worker import celery
from app.agent import research_agent

logger = logging.getLogger(__name__)


@celery.task(
    name="app.tasks.run_research",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    time_limit=600,
    soft_time_limit=300,
)
def run_research(self, topic: str) -> str:
    """Celery task to run research agent asynchronously."""
    try:
        logger.info(f"Research started: {topic}")
        result = research_agent(topic)
        logger.info(f"Research completed: {topic}")
        return result
    except Exception as e:
        logger.error(f"Research failed ({topic}): {e}")
        self.retry(exc=e)