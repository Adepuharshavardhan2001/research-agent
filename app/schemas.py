from typing import Optional, Literal, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# ============================================================
# Tool contracts: search_web
# ============================================================

class SearchInput(BaseModel):
    query: str = Field(..., min_length=3, max_length=200)
    max_results: int = Field(default=3, ge=1, le=10)


class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str


class SearchOutput(BaseModel):
    results: list[SearchResult] = Field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


# ============================================================
# Tool contracts: read_article
# ============================================================

class ReadInput(BaseModel):
    url: str = Field(..., min_length=8)
    max_chars: int = Field(default=8000, ge=100, le=20000)


class ReadOutput(BaseModel):
    url: str
    text: str = ""
    success: bool = True
    error: Optional[str] = None


# ============================================================
# Agent decision (what the LLM returns each turn)
# ============================================================

ActionType = Literal["search", "read", "finish"]


class AgentDecision(BaseModel):
    action: ActionType
    query: Optional[str] = None
    url: Optional[str] = None
    reasoning: Optional[str] = None

    @field_validator("query")
    @classmethod
    def _query_required_for_search(cls, v, info):
        if info.data.get("action") == "search" and not v:
            raise ValueError("query is required when action='search'")
        return v

    @field_validator("url")
    @classmethod
    def _url_required_for_read(cls, v, info):
        if info.data.get("action") == "read" and not v:
            raise ValueError("url is required when action='read'")
        return v


# ============================================================
# Agent state (carried across steps)
# ============================================================

class Finding(BaseModel):
    type: Literal["search", "article"]
    data: Any
    step: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentState(BaseModel):
    topic: str
    step: int = 0
    max_steps: int = 8
    findings: list[Finding] = Field(default_factory=list)
    urls_seen: set[str] = Field(default_factory=set)
    queries_tried: list[str] = Field(default_factory=list)
    finished: bool = False


# ============================================================
# API contracts: FastAPI endpoints
# ============================================================

class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=300)


class ResearchResponse(BaseModel):
    task_id: str
    status: Literal["queued"] = "queued"


class TaskStatusResponse(BaseModel):
    task_id: str
    status: Literal["queued", "running", "completed", "failed", "retrying"]
    result: Optional[dict] = None
    error: Optional[str] = None
    progress: Optional[int] = None
    stage: Optional[str] = None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    redis: bool
    detail: Optional[str] = None


# ============================================================
# Memory
# ============================================================

class MemoryEntry(BaseModel):
    topic: str
    report: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)