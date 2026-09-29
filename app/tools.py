import requests
import structlog
from bs4 import BeautifulSoup
from pydantic import ValidationError
from tavily import TavilyClient
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

from app.config import (
    TAVILY_API_KEY,
    DEFAULT_SEARCH_RESULTS,
    MAX_SEARCH_RESULTS,
    SEARCH_MAX_RETRIES,
    DEFAULT_MAX_CHARS,
    MAX_ARTICLE_CHARS,
    FETCH_TIMEOUT_SECONDS,
    READ_MAX_RETRIES,
)
from app.schemas import (
    SearchInput,
    SearchResult,
    SearchOutput,
    ReadInput,
    ReadOutput,
)

logger = structlog.get_logger()

tavily = TavilyClient(api_key=TAVILY_API_KEY)


# ============================================================
# Internal: HTML fetching with retries + timeouts
# ============================================================

@retry(
    stop=stop_after_attempt(READ_MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=False,
)
def _fetch_html(url: str) -> str | None:
    """Fetch raw HTML from a URL. Retries on transient network failures."""
    try:
        response = requests.get(
            url,
            timeout=FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ResearchAgent/1.0)"},
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type:
            logger.warning("non_html_content", url=url, content_type=content_type)
            return None

        return response.text

    except requests.Timeout:
        logger.warning("fetch_timeout", url=url)
        raise
    except requests.ConnectionError:
        logger.warning("fetch_connection_error", url=url)
        raise
    except requests.HTTPError as e:
        logger.warning("fetch_http_error", url=url, status=e.response.status_code)
        return None
    except Exception as e:
        logger.error("fetch_unexpected_error", url=url, error=str(e))
        return None


# ============================================================
# Tool 1: search_web
# ============================================================

def search_web(query: str, max_results: int = DEFAULT_SEARCH_RESULTS) -> SearchOutput:
    """
    Search the web for a query using Tavily.
    Always returns a SearchOutput — never raises.
    """
    try:
        validated = SearchInput(query=query, max_results=max_results)
    except ValidationError as e:
        logger.error("search_invalid_input", error=str(e))
        return SearchOutput(results=[], success=False, error=f"Invalid input: {e}")

    try:
        raw = tavily.search(
            query=validated.query,
            max_results=min(validated.max_results, MAX_SEARCH_RESULTS),
        )

        results = [
            SearchResult(
                url=r.get("url", ""),
                title=r.get("title", ""),
                snippet=r.get("content", ""),
            )
            for r in raw.get("results", [])
            if r.get("url")
        ]

        logger.info("search_success", query=query, count=len(results))
        return SearchOutput(results=results, success=True)

    except Exception as e:
        logger.error("search_failed", query=query, error=str(e))
        return SearchOutput(results=[], success=False, error=str(e))


# ============================================================
# Tool 2: read_article
# ============================================================

def read_article(url: str, max_chars: int = DEFAULT_MAX_CHARS) -> ReadOutput:
    """
    Fetch and extract readable text from a URL.
    Always returns a ReadOutput — never raises.
    """
    try:
        validated = ReadInput(url=url, max_chars=max_chars)
    except ValidationError as e:
        logger.error("read_invalid_input", url=url, error=str(e))
        return ReadOutput(url=url, text="", success=False, error=f"Invalid input: {e}")

    try:
        html = _fetch_html(validated.url)
    except RetryError:
        logger.warning("read_retries_exhausted", url=validated.url)
        return ReadOutput(
            url=validated.url,
            text="",
            success=False,
            error="Network failed after retries",
        )
    except Exception as e:
        logger.warning("read_fetch_exception", url=validated.url, error=str(e))
        return ReadOutput(
            url=validated.url,
            text="",
            success=False,
            error=f"Fetch error: {e}",
        )

    if html is None:
        return ReadOutput(url=validated.url, text="", success=False, error="Fetch failed")

    try:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        text = " ".join(text.split())

        if len(text) > validated.max_chars:
            text = text[: validated.max_chars] + " [truncated]"

        if len(text) < 100:
            logger.warning("read_too_short", url=validated.url, length=len(text))
            return ReadOutput(
                url=validated.url,
                text=text,
                success=False,
                error="Content too short",
            )

        logger.info("read_success", url=validated.url, length=len(text))
        return ReadOutput(url=validated.url, text=text, success=True)

    except Exception as e:
        logger.error("read_parse_error", url=validated.url, error=str(e))
        return ReadOutput(url=validated.url, text="", success=False, error=str(e))


# ============================================================
# Tool specs (for the LLM)
# ============================================================

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the web for a query. Returns a list of results, each with a URL, "
                "title, and snippet. Use this to find sources on a topic."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (3-200 characters).",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results to return (1-10). Default 3.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_article",
            "description": (
                "Fetch and extract the readable text content from a URL. "
                "Use this to read a specific web page found via search_web."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to read (must start with http:// or https://).",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to extract (100-20000). Default 8000.",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": (
                "Call this when you have gathered enough information and are ready "
                "to write the final report. Use this INSTEAD of searching or reading."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Brief explanation of why you're finishing now.",
                    },
                },
                "required": [],
            },
        },
    },
]