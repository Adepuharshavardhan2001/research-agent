import os
import logging
import requests
from bs4 import BeautifulSoup
from tavily import TavilyClient

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
if not TAVILY_API_KEY:
    raise ValueError("TAVILY_API_KEY environment variable is not set")

tavily = TavilyClient(api_key=TAVILY_API_KEY)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}


def search_web(query: str) -> list:
    """Search the web using Tavily API."""
    try:
        logger.info(f"Searching for: {query}")
        result = tavily.search(query=query, max_results=3)
        results = result.get("results", [])
        logger.info(f"Found {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"Search failed for '{query}': {e}")
        return []


def read_article(url: str) -> str:
    """Extract text content from a URL."""
    try:
        logger.info(f"Reading: {url}")
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        logger.info(f"Extracted {len(text)} chars")
        return text[:2000]
    except requests.RequestException as e:
        logger.error(f"Failed to read {url}: {e}")
        return f"[Failed to extract content: {url}]"