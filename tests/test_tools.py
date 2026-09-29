"""
Tests for app.tools — search_web, read_article, TOOLS_SPEC.
Mocks external services so no real API calls are made.
"""
from unittest.mock import patch

import requests

from app.tools import search_web, read_article, TOOLS_SPEC
from app.schemas import SearchOutput, ReadOutput


# ============================================================
# TOOLS_SPEC
# ============================================================

def test_tools_spec_contains_three_tools():
    names = [t["function"]["name"] for t in TOOLS_SPEC]
    assert "search_web" in names
    assert "read_article" in names
    assert "finish" in names
    assert len(TOOLS_SPEC) == 3


def test_tools_spec_shapes():
    for tool in TOOLS_SPEC:
        assert tool["type"] == "function"
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]


# ============================================================
# search_web
# ============================================================

@patch("app.tools.tavily.search")
def test_search_web_success(mock_search):
    mock_search.return_value = {
        "results": [
            {"url": "https://a.com", "title": "A", "content": "snippet A"},
            {"url": "https://b.com", "title": "B", "content": "snippet B"},
        ]
    }
    out = search_web("test query")

    assert isinstance(out, SearchOutput)
    assert out.success is True
    assert len(out.results) == 2
    assert out.results[0].url == "https://a.com"
    assert out.results[1].title == "B"
    assert out.error is None


@patch("app.tools.tavily.search")
def test_search_web_filters_items_without_url(mock_search):
    mock_search.return_value = {
        "results": [
            {"url": "https://a.com", "title": "A", "content": "x"},
            {"title": "no url", "content": "y"},
        ]
    }
    out = search_web("test query")
    assert out.success is True
    assert len(out.results) == 1


@patch("app.tools.tavily.search")
def test_search_web_api_failure_returns_error(mock_search):
    mock_search.side_effect = Exception("Tavily down")
    out = search_web("test query")

    assert out.success is False
    assert out.results == []
    assert "Tavily down" in out.error


def test_search_web_rejects_short_query():
    """Query under 3 chars fails Pydantic validation and returns error."""
    out = search_web("ab")
    assert out.success is False
    assert out.error is not None
    assert "Invalid input" in out.error


# ============================================================
# read_article
# ============================================================

@patch("app.tools._fetch_html")
def test_read_article_success(mock_fetch):
    mock_fetch.return_value = (
        "<html><body><article>"
        "<p>" + ("Real content here. " * 30) + "</p>"
        "</article></body></html>"
    )
    out = read_article("https://example.com/article")

    assert isinstance(out, ReadOutput)
    assert out.success is True
    assert "Real content here" in out.text
    assert len(out.text) > 100


@patch("app.tools._fetch_html")
def test_read_article_strips_scripts_and_nav(mock_fetch):
    mock_fetch.return_value = (
        "<html><body>"
        "<nav>Menu Links</nav>"
        "<script>var x = 1;</script>"
        "<style>.a{color:red}</style>"
        "<article>" + ("Useful paragraph. " * 30) + "</article>"
        "<footer>Copyright</footer>"
        "</body></html>"
    )
    out = read_article("https://example.com")

    assert out.success is True
    assert "Useful paragraph" in out.text
    assert "Menu Links" not in out.text
    assert "var x = 1" not in out.text
    assert "color:red" not in out.text
    assert "Copyright" not in out.text


@patch("app.tools._fetch_html")
def test_read_article_truncates_long_content(mock_fetch):
    mock_fetch.return_value = "<html><body><p>" + ("x" * 50000) + "</p></body></html>"
    out = read_article("https://example.com", max_chars=500)

    assert out.success is True
    assert len(out.text) <= 520
    assert out.text.endswith("[truncated]")


@patch("app.tools._fetch_html")
def test_read_article_too_short(mock_fetch):
    mock_fetch.return_value = "<html><body><p>hi</p></body></html>"
    out = read_article("https://example.com")

    assert out.success is False
    assert "too short" in out.error.lower()


@patch("app.tools._fetch_html")
def test_read_article_fetch_returns_none(mock_fetch):
    mock_fetch.return_value = None
    out = read_article("https://example.com")

    assert out.success is False
    assert "fetch failed" in out.error.lower()


def test_read_article_rejects_invalid_url():
    out = read_article("not-a-url")
    assert out.success is False
    assert out.error is not None


def test_read_article_handles_fetch_exception():
    """If _fetch_html raises, read_article must return a clean error, not crash."""
    with patch("app.tools._fetch_html", side_effect=requests.Timeout):
        out = read_article("https://example.com")

    assert out.success is False
    assert out.error is not None