from fastapi import FastAPI
from celery.result import AsyncResult

from app.tasks import run_research
from app.celery_worker import celery

app = FastAPI(
    title="Research Agent",
    version="1.0"
)


@app.get("/status/{task_id}")
def task_status(task_id: str):

    task = AsyncResult(task_id)

    return {
        "task_id": task.id,
        "status": task.status,
        "result": task.result if task.ready() else None
    }

@app.post("/research")
def research(topic: str):

    task = run_research.delay(topic)

    return {
        "task_id": task.id,
        "status": "processing"
    }


@app.get("/status/{task_id}")
def task_status(task_id: str):

    task = AsyncResult(
        task_id,
        app=celery
    )

    return {
        "task_id": task.id,
        "status": task.status,
        "result": str(task.result)
    }