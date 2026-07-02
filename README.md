#  Autonomous AI Research Agent

An AI-powered research system that automatically searches the web, analyzes content, and generates structured research reports using Groq LLM, Celery, and Redis.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.103-green)
![Docker](https://img.shields.io/badge/Docker-ready-blue)

---

##  Features

- **Autonomous Research** — Enter a topic, get a full research report
- **Web Search** — Uses Tavily API to find relevant articles
- **Content Extraction** — Scrapes and analyzes article content
- **AI Report Generation** — Groq LLM (Llama 3.3 70B) generates structured reports
- **Async Processing** — Celery + Redis for background tasks
- **Memory Storage** — Redis stores research history
- **Docker Ready** — Docker Compose with API, Celery worker, and Redis

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **API** | FastAPI, Uvicorn |
| **Async Tasks** | Celery, Redis |
| **LLM** | Groq (Llama 3.3 70B) |
| **Web Search** | Tavily API |
| **Web Scraping** | BeautifulSoup4, Requests |
| **Containerization** | Docker, Docker Compose |

---

##  Project Structure

research-agent/

├── app/

│ ├── main.py # FastAPI routes

│ ├── agent.py # Research agent workflow

│ ├── tasks.py # Celery tasks

│ ├── celery_worker.py # Celery configuration

│ ├── tools.py # Web search + article reader

│ ├── report.py # Groq LLM report generator

│ └── memory.py # Redis memory storage

├── Dockerfile

├── docker-compose.yml

├── requirements.txt

## 🚀 Quick Start

### Prerequisites

- Docker Desktop
- Groq API key (https://console.groq.com)
- Tavily API key (https://tavily.com)

### 1. Clone

```bash
git clone https://github.com/Adepuharshavardhan2001/research-agent.git
cd research-agent

2. Set API Keys

Create .env file:

GROQ_API_KEY=gsk_your_key
TAVILY_API_KEY=tvly_your_key

3. Run

docker-compose up -d

4. Access

http://localhost:8000/docs

API Endpoints

Start Research

http
POST /research
Content-Type: application/json

{
  "topic": "AI in healthcare"
}
Response:

json
{
  "task_id": "abc123...",
  "status": "processing"
}

Check Status

http

GET /status/{task_id}

Response:

json
{
  "task_id": "abc123...",
  "status": "SUCCESS",
  "result": "1. Executive Summary\n\nAI in healthcare..."
}

 Architecture


User Request
     │
     ▼
FastAPI (/research)
     │
     ▼
Celery Task (Redis queue)
     │
     ▼
Research Agent
├── Web Search (Tavily)
├── Article Reader (BeautifulSoup)
├── Report Generator (Groq LLM)
└── Memory Storage (Redis)
     │
     ▼
Structured Research Report

└── README.md
