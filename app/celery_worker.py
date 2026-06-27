import os
import logging
from dotenv import load_dotenv
from celery import Celery

load_dotenv()
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise ValueError("REDIS_URL environment variable is not set")

celery = Celery(
    "research",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery.autodiscover_tasks(["app.tasks"])

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=600,
    task_soft_time_limit=300,
)

logger.info("Celery configured with Redis broker")