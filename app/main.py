import structlog
from fastapi import FastAPI, HTTPException, status
from celery.result import AsyncResult

from app.celery_worker import celery
from app.memory import redis_client
from app.schemas import (
    ResearchRequest,
    ResearchResponse,
    TaskStatusResponse,
    HealthResponse,
    ReadyResponse,
)

logger = structlog.get_logger()

app = FastAPI(
    title="Agentic Research API",
    description="An autonomous research agent that plans, searches, and produces cited reports.",
    version="1.0.0",
)


# ============================================================
# Health & readiness
# ============================================================

@app.get("/health", response_model=HealthResponse, tags=["system"])
def health():
    return HealthResponse()


@app.get("/ready", response_model=ReadyResponse, tags=["system"])
def ready():
    try:
        redis_client.ping()
        return ReadyResponse(status="ready", redis=True)
    except Exception as e:
        logger.error("readiness_failed", error=str(e))
        return ReadyResponse(status="not_ready", redis=False, detail=str(e))


# ============================================================
# Research: submit a topic
# ============================================================

@app.post(
    "/research",
    response_model=ResearchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["research"],
)
def submit_research(request: ResearchRequest):
    try:
        from app.tasks import run_research  # noqa: WPS433

        task = run_research.delay(request.topic)

        logger.info("research_queued", task_id=task.id, topic=request.topic)
        return ResearchResponse(task_id=task.id, status="queued")

    except Exception as e:
        logger.error("research_queue_failed", topic=request.topic, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue task: {e}",
        )


# ============================================================
# Status: poll a task
# ============================================================

# Map Celery states to clean API states
STATUS_MAP = {
    "PENDING": "queued",
    "RECEIVED": "queued",
    "STARTED": "running",
    "PROGRESS": "running",
    "SUCCESS": "completed",
    "FAILURE": "failed",
    "RETRY": "retrying",
    "REVOKED": "failed",
}


@app.get(
    "/status/{task_id}",
    response_model=TaskStatusResponse,
    tags=["research"],
)
def task_status(task_id: str):
    try:
        task = AsyncResult(task_id, app=celery)
        state = STATUS_MAP.get(task.state, "queued")

        response = TaskStatusResponse(task_id=task_id, status=state)

        if task.state == "PROGRESS" and isinstance(task.info, dict):
            response.progress = task.info.get("progress")
            response.stage = task.info.get("stage")

        elif task.state == "SUCCESS":
            result = task.result
            if isinstance(result, dict):
                response.result = result
            else:
                response.result = {"raw": str(result)}

        elif task.state == "FAILURE":
            response.error = str(task.info)

        logger.info("status_checked", task_id=task_id, state=state)
        return response

    except Exception as e:
        logger.error("status_check_failed", task_id=task_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check task status: {e}",
        )