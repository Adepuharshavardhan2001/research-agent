# Autonomous AI Research Agent

An agentic research system where an LLM decides what to search, what to read, and when to stop — then produces a cited research report. Built with FastAPI, Celery, Redis, Groq, and Tavily.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Celery](https://img.shields.io/badge/Celery-5.4-green)
![Redis](https://img.shields.io/badge/Redis-8-red)
![Tests](https://img.shields.io/badge/tests-31%20passing-brightgreen)
![Eval](https://img.shields.io/badge/eval-100%25%20success-brightgreen)

---

## 🔗 Live Demo

**Try it now:** [http://13.233.96.119/docs](http://13.233.96.119/docs)

Deployed on AWS EC2 (t3.micro, Ubuntu) behind nginx with systemd-managed FastAPI + Celery services.

![Swagger UI](docs/screenshots/live_deployment.png)

---

## The Problem

Researching a new topic manually takes **1–2 hours**: open 10+ tabs, read articles, take notes, write a summary. Existing tools fail you:

- **Google** gives you links, not answers.
- **ChatGPT** gives answers, but hallucinates and doesn't cite sources.
- **Perplexity Pro** starts at $20/month.
- **OpenAI Deep Research** costs $200/month.

**This project solves that.** Give it a topic; it autonomously researches and returns a cited report for **~$0.0015 per run** — a fraction of the cost of alternatives.

---

## How It Works

Unlike a fixed pipeline, this is a true **agentic loop**: at every step, an LLM decides the next action.




**The LLM decides every step** using Groq's function-calling API with three tools: `search_web`, `read_article`, and `finish`.

---

## Features

### Agentic Core
- **LLM-driven loop** — the model picks its next action (search / read / finish)
- **Self-termination** — the LLM calls `finish` with reasoning when it has enough
- **Adaptive behavior** — if a source fails, the LLM picks another
- **Max-step guardrail** — bounded execution, no infinite loops
- **Deduplication** — the same URL or query is never processed twice
- **Fallback pipeline** — if the LLM fails, a linear pipeline runs instead

### Production Reliability
- **Retries with exponential backoff** — via `tenacity`, on network failures
- **Timeouts on every HTTP call** — no hung processes
- **Structured logging** — every decision logged via `structlog`
- **Idempotency** — the same topic returns the cached report (24h TTL)
- **Task crash recovery** — Celery `acks_late` + `reject_on_worker_lost`

### Contracts & Validation
- **Pydantic tool contracts** — every tool has typed inputs and outputs
- **Validated API requests** — `ResearchRequest`, `TaskStatusResponse`
- **Structured errors** — tools return `success: bool` + `error: str`, never crash

### Report Quality
- **Citation grounding** — every claim includes `(source: <url>)`
- **Refusal path** — the LLM says "insufficient data" instead of hallucinating
- **Truncation control** — bounded context sent to the LLM

---

## Evaluation Results

Run on **10 topics** spanning AI/ML, data, MLOps, and ethics:

| Metric | Result |
|---|---|
| **Success rate** | **100%** (10/10 topics) |
| **Avg latency** | 59.3 seconds |
| **Avg cost per report** | **$0.00153** |
| **Avg keyword coverage** | 90% |
| **Avg citations per report** | 21.2 |
| **Avg report length** | 6,189 chars |

**Comparison:**

| Tool | Cost per report |
|---|---|
| **This project** | **$0.0015** |
| Perplexity Pro | ~$0.20 |
| OpenAI Deep Research | ~$2.00+ |

**Failure handling in practice:** During the eval, 20 URLs were read. Two failed (one 403 from CDC.gov, one 404 from a stale link). The tool returned `success=False` (no crash), the LLM saw the failure and picked an alternative source. **All 10 topics still completed successfully.**

Run the eval yourself:


python eval/run_eval.py

Tech Stack

Layer	Technology
API	FastAPI, Uvicorn
Async Tasks	Celery 5.4, Redis 8
LLM	Groq (openai/gpt-oss-120b) with function calling
Web Search	Tavily API
Content Extraction	Requests, BeautifulSoup4
Validation	Pydantic v2
Reliability	tenacity (retries), structlog (logging)
Testing	pytest (31 tests)
Deployment	AWS EC2, systemd, nginx
Containerization	Docker, Docker Compose

Project Structure

research-agent/
├── app/
│   ├── __init__.py
│   ├── config.py            # Central settings
│   ├── schemas.py           # Pydantic contracts
│   ├── tools.py             # search_web, read_article + tool specs
│   ├── agent.py             # The LLM-driven agent loop
│   ├── report.py            # Citation-grounded report generation
│   ├── memory.py            # Redis-backed memory (24h TTL)
│   ├── tasks.py             # Celery task with retries + idempotency
│   ├── celery_worker.py     # Celery configuration
│   └── main.py              # FastAPI endpoints
├── tests/                   # 31 unit + integration tests
│   ├── test_tools.py
│   ├── test_memory.py
│   └── test_agent.py
├── eval/
│   ├── test_topics.json     # 10 eval topics
│   └── run_eval.py          # Eval harness
├── scripts/
│   └── run_agent.py         # Local dev runner
├── docs/
│   ├── SYSTEM_DESIGN.md     # Deep dive: architecture, tradeoffs, edge cases
│   └── screenshots/         # Real run logs and API responses
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example

Quick Start

Prerequisites

Python 3.12 (3.11 also works; 3.13/3.14 may need Rust for some packages)

Redis 7+ running on localhost:6379

Groq API key — https://console.groq.com

Tavily API key — https://tavily.com

1. Clone

git clone https://github.com/Adepuharshavardhan2001/research-agent.git
cd research-agent

2. Set up environment


python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
Create .env (copy from .env.example):

env

GROQ_API_KEY=your_groq_api_key
TAVILY_API_KEY=your_tavily_api_key
REDIS_URL=redis://localhost:6379/0
GROQ_MODEL=openai/gpt-oss-120b

3. Start Redis

docker run -d -p 6379:6379 --name research-redis redis:7-alpine

4. Run the API + worker (2 terminals)

Terminal 1 — Celery worker:


python -m celery -A app.celery_worker.celery worker --loglevel=info --pool=solo
(On Linux/Mac, replace --pool=solo with --concurrency=1.)

Terminal 2 — FastAPI:

bash
python -m uvicorn app.main:app --reload --port 8000
5. Try it
Open Swagger UI: http://localhost:8000/docs

Or use curl:


curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "retrieval augmented generation evaluation methods"}'
Response:

json
{"task_id": "83038c2a-...", "status": "queued"}
Poll for the result:

bash
curl http://localhost:8000/status/83038c2a-...
Final response:

json
{
  "task_id": "83038c2a-...",
  "status": "completed",
  "result": {
    "topic": "retrieval augmented generation evaluation methods",
    "report": "Executive Summary\n- Evaluation of RAG systems requires... (source: https://...)",
    "cached": false
  }
}

6. Or use Docker Compose

docker-compose up -d
This starts Redis, the Celery worker, and the API together.

Deployment (AWS EC2)

The app is deployed on AWS EC2 (t3.micro, Ubuntu) with:

systemd services for FastAPI and Celery (Restart=always)

nginx reverse proxy on port 80 → 127.0.0.1:8000

Redis running locally on 127.0.0.1:6379

2 GB swap added (t3.micro has only 1 GB RAM)

Service files
/etc/systemd/system/research-api.service:


[Unit]
Description=Research Agent FastAPI
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/research-agent
EnvironmentFile=/home/ubuntu/research-agent/.env
ExecStart=/home/ubuntu/research-agent/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
/etc/systemd/system/research-celery.service:

ini
[Unit]

Description=Research Agent Celery Worker
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/research-agent
EnvironmentFile=/home/ubuntu/research-agent/.env
ExecStart=/home/ubuntu/research-agent/venv/bin/celery -A app.celery_worker.celery worker --loglevel=info --concurrency=1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target

nginx config
/etc/nginx/sites-available/research:

server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

Deploy commands

sudo apt install -y python3.12 python3.12-venv python3-pip redis-server nginx git

git clone https://github.com/Adepuharshavardhan2001/research-agent.git

cd research-agent

python3.12 -m venv venv

source venv/bin/activate

pip install -r requirements.txt

# create .env with API keys

sudo systemctl enable research-api research-celery
sudo systemctl start research-api research-celery

Running Tests

python -m pytest tests/ -v
Expected:


31 passed in ~3s
All tests use mocks for external services (Groq, Tavily, requests) — no API calls, no network.

API Reference
Method	Endpoint	Description
GET	/health	Liveness check
GET	/ready	Readiness check (pings Redis)
POST	/research	Submit a topic — returns task_id (202)
GET	/status/{task_id}	Poll task status + result
GET	/docs	Swagger UI (auto-generated)
