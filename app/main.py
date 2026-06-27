import logging
from fastapi import FastAPI, HTTPException
from celery.result import AsyncResult
from pydantic import BaseModel, Field

from app.tasks import run_research
from app.celery_worker import celery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Research Agent", version="1.0")


class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=200, examples=["AI in healthcare"])


@app.get("/")
def home():
    return {"message": "Research Agent API is running", "version": "1.0"}


@app.post("/research")
def research(request: ResearchRequest):
    try:
        task = run_research.delay(request.topic)
        logger.info(f"Task started: {task.id} for '{request.topic}'")
        return {"task_id": task.id, "status": "processing"}
    except Exception as e:
        logger.error(f"Failed to start task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{task_id}")
def task_status(task_id: str):
    task = AsyncResult(task_id, app=celery)
    return {
        "task_id": task.id,
        "status": task.status,
        "result": task.result if task.ready() else None
    }