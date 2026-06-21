import os
from dotenv import load_dotenv
from celery import Celery

load_dotenv()

print("REDIS_URL =", os.getenv("REDIS_URL"))

celery = Celery(
    "research",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL")
)

# ADD THIS LINE
celery.autodiscover_tasks(["app"])

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)