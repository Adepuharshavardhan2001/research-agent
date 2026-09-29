import os
from dotenv import load_dotenv

load_dotenv()


# ---------- API keys ----------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ---------- Redis ----------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ---------- Models ----------
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.3"))
GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "2000"))
GROQ_TIMEOUT_SECONDS = int(os.getenv("GROQ_TIMEOUT_SECONDS", "30"))

# ---------- Search ----------
DEFAULT_SEARCH_RESULTS = int(os.getenv("DEFAULT_SEARCH_RESULTS", "3"))
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "10"))
SEARCH_MAX_RETRIES = int(os.getenv("SEARCH_MAX_RETRIES", "3"))

# ---------- Reading ----------
DEFAULT_MAX_CHARS = int(os.getenv("DEFAULT_MAX_CHARS", "8000"))
MAX_ARTICLE_CHARS = int(os.getenv("MAX_ARTICLE_CHARS", "20000"))
FETCH_TIMEOUT_SECONDS = int(os.getenv("FETCH_TIMEOUT_SECONDS", "10"))
READ_MAX_RETRIES = int(os.getenv("READ_MAX_RETRIES", "3"))

# ---------- Agent ----------
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "8"))
AGENT_MAX_LLM_RETRIES = int(os.getenv("AGENT_MAX_LLM_RETRIES", "3"))

# ---------- Memory ----------
MEMORY_TTL_SECONDS = int(os.getenv("MEMORY_TTL_SECONDS", str(60 * 60 * 24)))
MAX_RECENT_TOPICS = int(os.getenv("MAX_RECENT_TOPICS", "100"))

# ---------- Celery task limits ----------
TASK_SOFT_TIME_LIMIT = int(os.getenv("TASK_SOFT_TIME_LIMIT", "300"))
TASK_TIME_LIMIT = int(os.getenv("TASK_TIME_LIMIT", "360"))
TASK_MAX_RETRIES = int(os.getenv("TASK_MAX_RETRIES", "3"))