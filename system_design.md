# System Design — Autonomous AI Research Agent

A deep dive into the architecture, design decisions, failure handling, and tradeoffs of an agentic research system.

**Author:** Adepu Harsha Vardhan
**Last updated:** 2026-09-29
**Repo:** [github.com/Adepuharshavardhan2001/research-agent](https://github.com/Adepuharshavardhan2001/research-agent)

---

## 1. Problem Statement

Researching a new topic manually takes 1–2 hours: open 10+ tabs, read articles, take notes, write a summary. Existing tools fall into two failure modes:

- **Search engines** (Google, Bing) return links, not answers. The synthesis work is still on you.
- **LLM chatbots** (ChatGPT, Claude) give answers, but hallucinate and rarely cite sources.

Paid alternatives (Perplexity Pro at $20/month, OpenAI Deep Research at $200/month) are expensive and closed-source.

**Goal:** An autonomous research agent that:
1. Plans its own research (decides queries, sources, and when to stop)
2. Grounds every claim in cited sources
3. Costs a fraction of commercial alternatives (<$0.01 per report)
4. Handles failure gracefully (dead URLs, LLM errors, rate limits)

---

## 2. High-Level Architecture

┌─────────────────────────────────────────────────────────────┐
│ CLIENT │
│ POST /research {"topic": "..."} │
│ GET /status/{task_id} │
└──────────────────────────┬──────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ FastAPI (main.py) │
│ • Validates request via Pydantic (ResearchRequest) │
│ • Queues Celery task (run_research.delay) │
│ • Returns 202 Accepted + task_id │
│ • /health and /ready endpoints for monitoring │
└──────────────────────────┬──────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Redis (broker + backend) │
│ • Celery task queue │
│ • Task result backend │
│ • Agent memory (24h TTL) │
└──────────────────────────┬──────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Celery Worker (celery_worker.py) │
│ • Pulls tasks from Redis │
│ • Retries on failure (exponential backoff) │
│ • Reports progress via update_state │
└──────────────────────────┬──────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ run_research (tasks.py) │
│ 1. Check memory (Redis) — return cached if hit │
│ 2. Call research_agent(topic) │
│ 3. Save report to memory │
│ 4. Return {topic, report, cached} │
└──────────────────────────┬──────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ research_agent (agent.py) — THE LOOP │
│ │
│ while step < max_steps and not finished: │
│ decision = LLM decides next action │
│ (search_web / read_article / finish) │
│ execute tool via tools.py │
│ append result to AgentState │
│ │
│ Guardrails: │
│ • max_steps (default 8) │
│ • dedupe URLs (urls_seen set) │
│ • dedupe queries (queries_tried list) │
│ • forced read if repeated searches detected │
└──────────────────────────┬──────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ generate_report (report.py) │
│ • Formats findings into a structured prompt │
│ • Requires citations: "(source: <url>)" │
│ • Refuses on insufficient evidence │
│ • Logs token usage for cost tracking │
└─────────────────────────────────────────────────────────────┘

text

---

## 3. Component Design

### 3.1 FastAPI (API Layer)

**Responsibilities:**
- Accept `POST /research` requests
- Validate input via Pydantic (`ResearchRequest`)
- Queue Celery tasks
- Expose `GET /status/{task_id}` for polling
- Provide health endpoints (`/health`, `/ready`)

**Design decisions:**
- **Async task pattern (202 Accepted)** — research takes 30–60s, too long for synchronous HTTP.
- **Pydantic validation at the boundary** — reject bad input before it reaches the agent.
- **STATUS_MAP** — Celery returns internal states (`PENDING`, `STARTED`, `SUCCESS`), which we map to clean API states (`queued`, `running`, `completed`, `failed`).
- **`/ready` pings Redis** — catches deployment issues where Redis isn't reachable.

**Why not FastAPI BackgroundTasks?**
- Doesn't survive server restarts
- No retry mechanism
- No visibility into task state
- Doesn't scale beyond one process

**Why Celery?**
- Survives restarts (tasks persisted in Redis)
- Built-in retries with backoff
- Multiple workers → horizontal scale
- Standard in Python production systems

### 3.2 Celery Worker (Task Execution)

**Configuration highlights:**
- `task_acks_late=True` — task is acknowledged **after** completion, so a worker crash requeues it
- `task_reject_on_worker_lost=True` — same purpose, catches hard worker deaths
- `worker_prefetch_multiplier=1` — fair dispatch, prevents one worker hogging tasks
- `task_soft_time_limit=300` / `task_time_limit=360` — hard bounds
- `autoretry_for=(Exception,)` with `retry_backoff=True` — 3 retries with exponential backoff

**Idempotency:**
```python
cached = get_memory(topic)
if cached:
    return {"topic": topic, "report": cached.report, "cached": True}
Before running the expensive agent, check if we already researched this topic. Reduces cost and latency on repeat queries.

Progress updates:

python
self.update_state(state="PROGRESS", meta={"stage": "searching", "progress": 20})
The API layer reads these to show live progress.

3.3 The Agent Loop (agent.py)
The core idea: the LLM decides what to do at each step — not a fixed sequence.

python
while state.step < state.max_steps:
    decision = _llm_decide_next_action(state)  # calls Groq with tools

    if decision.action == "finish":
        break
    elif decision.action == "search":
        _execute_search(state, decision.query)
    elif decision.action == "read":
        _execute_read(state, decision.url)
What the LLM sees at each step:

The topic

Step count and max steps

Searches completed, articles read

Queries already tried (DO NOT repeat)

URLs already read (DO NOT repeat)

Available UNREAD URLs from search results

A warning when steps_remaining <= 2

Why this works better than a fixed pipeline:

Adaptation — if a URL fails, the LLM picks a different one

Depth control — the LLM can search again if the first search was thin

Early termination — the LLM stops as soon as it has enough (saves cost)

Guardrails (failure-mode prevention):

Guardrail	Prevents
max_steps cap	Infinite loops
URL dedupe (urls_seen)	Reading the same page twice
Query dedupe (queries_tried)	Repeating the same search
Forced read on repeat-search	LLM looping on search
Fallback pipeline if no findings	Empty reports when LLM fails
LLM retries (AGENT_MAX_LLM_RETRIES)	Transient Groq failures
3.4 Tools (tools.py)
Two tools with explicit Pydantic contracts:

Tool	Input	Output
search_web	SearchInput(query, max_results)	SearchOutput(results, success, error)
read_article	ReadInput(url, max_chars)	ReadOutput(url, text, success, error)
Design principle: tools never raise exceptions. They return a structured result with success: bool and error: str | None. This means the agent can always inspect the result and decide what to do.

Retries with tenacity:

python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
)
Only retries on transient errors (timeout, connection). Does NOT retry on 404 (permanent) — that would waste time.

Timeouts on all HTTP calls:

python
response = requests.get(url, timeout=FETCH_TIMEOUT_SECONDS)
Content hygiene:

Strip <script>, <style>, <nav>, <footer>, <header>, <aside>

Collapse whitespace

Truncate to max_chars with an explicit [truncated] marker

Skip non-HTML content types

3.5 Report Generation (report.py)
Citation grounding:
The prompt explicitly requires every key claim to include (source: <url>). Without this, the LLM writes confident prose that isn't verifiable.

Refusal path:

"If the research data does not contain enough information for a section, write 'Insufficient data' — do NOT make things up."

Token accounting:

python
logger.info("report_generated",
    prompt_tokens=usage.prompt_tokens,
    completion_tokens=usage.completion_tokens,
    total_tokens=usage.total_tokens)
Every report logs its cost. Enables the eval harness to measure $/report.

Truncation:
Cap research content at 30,000 chars before sending to the LLM. Prevents context overflows.

3.6 Memory (memory.py)
Redis-backed, not in-memory.

Why it matters:

Shared across processes — FastAPI and Celery are separate Python processes; an in-memory dict would not be shared

Persistent across restarts — Redis survives worker restarts

TTL — keys expire after 24h, bounded storage

Recent list — a capped list of recently-researched topics

Why not SQLite or Postgres?

We only need ephemeral cache (24h TTL), not a permanent store

Redis gives O(1) reads with TTL

No schema migration needed

Already required as Celery's broker — zero additional infra

4. Design Decisions & Tradeoffs
Why Groq over OpenAI?
Factor	Groq (openai/gpt-oss-120b)	OpenAI (gpt-4o)
Latency	~1–2s per call	~3–5s per call
Cost	~$0.15/1M input tokens	~$2.50/1M input tokens
Tool calling	✅	✅
Model options	Fewer	More
Tradeoff accepted: fewer model choices for 10x speed and ~4x cost reduction.

Why function calling over LangChain / LangGraph?
Direct control — no hidden prompt templates or abstraction leaks

Debuggable — every LLM call is a single, traceable request

Lighter — no additional dependencies

Portable — the same code works with any OpenAI-compatible client

Tradeoff accepted: more code to write (the loop, tool specs) in exchange for full transparency.

Why Celery + Redis over FastAPI BackgroundTasks?
Durability — tasks survive process crashes

Retries — built-in with configurable backoff

Horizontal scale — start 10 workers, tasks distribute

Observability — every task has a state, result, and ID

Tradeoff accepted: operational complexity (Redis is another service to run).

Why Pydantic contracts for tools?
Type safety — inputs validated before hitting external APIs

Testability — mock the input, verify the output shape

Documentation — schemas auto-exported to Swagger

Failure isolation — invalid input returns success=False, doesn't crash

Tradeoff accepted: more boilerplate per tool.

Why max_steps = 8?
Lower (4–5) — cheaper but may stop before enough research

Higher (15+) — more thorough but risks runaway loops and cost

8 — empirically, most topics complete in 4–6 steps

Configurable via AGENT_MAX_STEPS env var.

5. Failure Handling
The system is designed for partial failure, not perfect uptime.

5.1 Tool failures (HTTP errors)
Real case from eval: 20 URLs read across 10 topics. Two failed:

cdc.gov → HTTP 403 (anti-bot protection)

vaiazazone.com → HTTP 404 (stale link)

What happens:

_fetch_html catches HTTPError, logs fetch_http_error, returns None

read_article sees None, returns ReadOutput(success=False, error="Fetch failed")

The agent's state summary shows the failure

The LLM picks a different URL on the next step

Result: all 10 topics still completed successfully.

5.2 LLM failures (transient)
Retries — AGENT_MAX_LLM_RETRIES=3 attempts per decision

Fallback — if all retries fail, the linear pipeline runs

No crash — the task still completes (with a simpler report)

5.3 Duplicate detection
URL dedupe — state.urls_seen prevents re-reading

Query dedupe — state.queries_tried prevents re-searching

Forced read — if the LLM repeatedly tries the same search, we execute an unread URL instead

5.4 Worker crashes
task_acks_late=True — task is requeued if the worker dies before completing

task_reject_on_worker_lost=True — same for hard worker kills

Result: no lost tasks on infrastructure failure

5.5 Empty findings
If the agent loop produces zero findings (e.g., all searches fail):

python
if not state.findings:
    return _fallback_pipeline(topic)
The fallback runs a single search + read, then generates a report. Never returns an empty response.

6. Evaluation Methodology
Test set
10 topics spanning AI/ML, data, MLOps, and ethics (eval/test_topics.json).

Metrics
Metric	What it measures
Success rate	Did the agent complete?
Latency	End-to-end time per topic
Cost	Estimated USD from token usage
Keyword coverage	% of expected keywords in report
Citations	Count of (source: ...) in report
Report length	Characters
Results (2026-09-29)
Metric	Value
Success rate	100% (10/10)
Avg latency	59.28s
Avg cost	$0.00153
Avg keyword coverage	90%
Avg citations per report	21.2
Avg report length	6,189 chars
Why these metrics (and not "LLM-as-judge")
Keyword coverage — a cheap proxy for "is the report on-topic?"

Citations — objective count; more citations = more grounding

Cost / latency — operational, non-negotiable for production

LLM-as-judge would be more accurate but introduces model-dependent variance

Known limitation: keyword coverage doesn't measure quality. A future improvement would be human-rated or LLM-judged samples on a small subset.

7. Known Limitations
Text-only sources. PDFs, images, and scanned pages are skipped.

No live data. The agent reads web articles, not real-time APIs (no live ticket booking, stock prices, etc.).

Tavily freshness. If Tavily's index contains a stale URL, read_article will 404 — handled gracefully, but the source is lost.

Single-worker eval. Windows uses --pool=solo for Celery. Production on Linux would use prefork.

No streaming. Reports return whole, not as tokens stream.

No persistent vector DB. Memory is Redis with TTL, not a long-term store.

LLM can waste steps. The forced-read guardrail catches loops, but a smarter planner could be more efficient.

No rate limiting. The API currently accepts unlimited requests from any IP.

8. Future Improvements
Short-term (1–2 weeks):

Rate limiting per IP (slowapi)

Streaming responses (SSE)

Add a /recent endpoint to list recent topics

Medium-term (1–2 months):

Add OCR for PDFs / images (multimodal)

Add a reranker to pick better sources (cross-encoder)

Support hybrid retrieval (BM25 + vector) for a RAG mode

Replace forced-read heuristic with a learned policy

Long-term (3–6 months):

Multi-agent specialization (one agent for search, one for reading, one for synthesis)

Persistent vector DB (Pinecone / pgvector) for long-term memory

A/B testing framework for prompt variants

Cost-aware routing (use smaller models for simple queries)

9. What This Project Demonstrates
Agentic AI — LLM-driven tool selection with function calling

Production engineering — retries, timeouts, structured logging, idempotency

Distributed systems — Celery + Redis task queue with crash recovery

API design — FastAPI with Pydantic contracts and health checks

Testing discipline — 31 unit + integration tests with mocked external services

Evaluation rigor — 10-topic benchmark with cost / latency / quality metrics

Tradeoff reasoning — documented decisions with alternatives considered

10. References
Function calling: Groq docs

Celery reliability: Celery — Tasks

Structured logging: structlog

Retry patterns: tenacity

Pydantic contracts: Pydantic v2