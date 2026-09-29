import os
import logging
from dotenv import load_dotenv
from celery import Celery
from celery.signals import worker_ready

from app.config import (
    REDIS_URL,
    TASK_SOFT_TIME_LIMIT,
    TASK_TIME_LIMIT,
)

load_dotenv()

logger = logging.getLogger(__name__)

celery = Celery(
    "research",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# Discover tasks in the `app` package
celery.autodiscover_tasks(["app"])

celery.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Broker connection reliability
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_transport_options={
        "visibility_timeout": 3600,
        "socket_keepalive": True,
    },

    # Task reliability — retry on worker crash
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Task result lifetime
    result_expires=3600,

    # Task limits
    task_soft_time_limit=TASK_SOFT_TIME_LIMIT,
    task_time_limit=TASK_TIME_LIMIT,

    # Logging
    worker_hijack_root_logger=False,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
)


@worker_ready.connect
def on_worker_ready(**kwargs):
    logger.info("Celery worker ready")