"""
Tests for app.agent — the LLM-driven agent loop.

Mocks the Groq LLM so no real API calls are made.
Mocks the tools so no real network calls are made.
"""
from unittest.mock import patch, MagicMock

import pytest

from app.agent import research_agent
from app.schemas import SearchOutput, SearchResult, ReadOutput


# ============================================================
# Helpers
# ============================================================

def _make_tool_call(name: str, arguments: dict):
    """Build a fake Groq tool_call object."""
    import json
    tc = MagicMock()
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    return tc


def _make_llm_response(tool_calls: list):
    """Build a fake Groq chat completion response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.tool_calls = tool_calls
    return response


def _fake_search_output():
    return SearchOutput(
        results=[
            SearchResult(url="https://a.com", title="A", snippet="snip A"),
            SearchResult(url="https://b.com", title="B", snippet="snip B"),
        ],
        success=True,
    )


def _fake_read_output(url: str):
    return ReadOutput(url=url, text="x" * 500, success=True)


# ============================================================
# Happy path: search → read → finish
# ============================================================

@patch("app.agent.groq_client")
@patch("app.agent.search_web")
@patch("app.agent.read_article")
@patch("app.agent.generate_report")
def test_agent_full_run(mock_report, mock_read, mock_search, mock_groq):
    mock_report.return_value = "FINAL REPORT"
    mock_search.return_value = _fake_search_output()
    mock_read.return_value = _fake_read_output("https://a.com")

    mock_groq.chat.completions.create.side_effect = [
        _make_llm_response([_make_tool_call("search_web", {"query": "test topic"})]),
        _make_llm_response([_make_tool_call("read_article", {"url": "https://a.com"})]),
        _make_llm_response([_make_tool_call("finish", {"reasoning": "enough"})]),
    ]

    result = research_agent("test topic")

    assert result == "FINAL REPORT"
    assert mock_search.call_count == 1
    assert mock_read.call_count == 1
    assert mock_report.call_count == 1


# ============================================================
# LLM says finish immediately → fallback pipeline runs
# ============================================================

@patch("app.agent.groq_client")
@patch("app.agent.search_web")
@patch("app.agent.read_article")
@patch("app.agent.generate_report")
def test_agent_falls_back_when_llm_finishes_without_research(
    mock_report, mock_read, mock_search, mock_groq
):
    """If the LLM finishes with no findings, the fallback pipeline runs."""
    mock_report.return_value = "SHORT REPORT"
    mock_search.return_value = _fake_search_output()
    mock_read.return_value = _fake_read_output("https://a.com")

    mock_groq.chat.completions.create.side_effect = [
        _make_llm_response([_make_tool_call("finish", {})]),
    ]

    result = research_agent("topic")
    assert result == "SHORT REPORT"
    # Fallback runs because there were no findings
    assert mock_search.call_count == 1
    assert mock_report.call_count == 1


# ============================================================
# Max steps guardrail
# ============================================================

@patch("app.agent.groq_client")
@patch("app.agent.search_web")
@patch("app.agent.read_article")
@patch("app.agent.generate_report")
def test_agent_respects_max_steps(mock_report, mock_read, mock_search, mock_groq):
    """If the LLM never finishes, the loop must stop at max_steps."""
    mock_report.return_value = "REPORT"
    mock_search.return_value = _fake_search_output()
    mock_read.return_value = _fake_read_output("https://a.com")

    def side_effect(*args, **kwargs):
        idx = mock_groq.chat.completions.create.call_count
        return _make_llm_response([
            _make_tool_call("search_web", {"query": f"q{idx}"})
        ])

    mock_groq.chat.completions.create.side_effect = side_effect

    research_agent("topic")

    from app.config import AGENT_MAX_STEPS
    assert mock_groq.chat.completions.create.call_count <= AGENT_MAX_STEPS


# ============================================================
# Deduplication: same URL is read only once
# ============================================================

@patch("app.agent.groq_client")
@patch("app.agent.search_web")
@patch("app.agent.read_article")
@patch("app.agent.generate_report")
def test_agent_dedupes_urls(mock_report, mock_read, mock_search, mock_groq):
    mock_report.return_value = "REPORT"
    mock_search.return_value = _fake_search_output()
    mock_read.return_value = _fake_read_output("https://a.com")

    mock_groq.chat.completions.create.side_effect = [
        _make_llm_response([_make_tool_call("search_web", {"query": "topic"})]),
        _make_llm_response([_make_tool_call("read_article", {"url": "https://a.com"})]),
        _make_llm_response([_make_tool_call("read_article", {"url": "https://a.com"})]),
        _make_llm_response([_make_tool_call("finish", {})]),
    ]

    research_agent("topic")
    assert mock_read.call_count == 1


# ============================================================
# Deduplication: same query is searched only once
# ============================================================

@patch("app.agent.groq_client")
@patch("app.agent.search_web")
@patch("app.agent.read_article")
@patch("app.agent.generate_report")
def test_agent_dedupes_queries(mock_report, mock_read, mock_search, mock_groq):
    mock_report.return_value = "REPORT"
    mock_search.return_value = _fake_search_output()

    mock_groq.chat.completions.create.side_effect = [
        _make_llm_response([_make_tool_call("search_web", {"query": "topic"})]),
        _make_llm_response([_make_tool_call("search_web", {"query": "topic"})]),
        _make_llm_response([_make_tool_call("finish", {})]),
    ]

    research_agent("topic")
    assert mock_search.call_count == 1


# ============================================================
# Fallback when the LLM keeps failing
# ============================================================

@patch("app.agent.groq_client")
@patch("app.agent.search_web")
@patch("app.agent.read_article")
@patch("app.agent.generate_report")
def test_agent_falls_back_on_llm_failure(mock_report, mock_read, mock_search, mock_groq):
    mock_report.return_value = "FALLBACK REPORT"
    mock_search.return_value = _fake_search_output()
    mock_read.return_value = _fake_read_output("https://a.com")

    mock_groq.chat.completions.create.side_effect = Exception("Groq down")

    result = research_agent("topic")

    assert result == "FALLBACK REPORT"
    assert mock_search.call_count == 1
    assert mock_report.call_count == 1


# ============================================================
# LLM returns no tool_calls → treated as finish → fallback
# ============================================================

@patch("app.agent.groq_client")
@patch("app.agent.search_web")
@patch("app.agent.read_article")
@patch("app.agent.generate_report")
def test_agent_no_tool_calls_treated_as_finish(
    mock_report, mock_read, mock_search, mock_groq
):
    mock_report.return_value = "REPORT"
    mock_search.return_value = _fake_search_output()
    mock_read.return_value = _fake_read_output("https://a.com")

    empty_response = MagicMock()
    empty_response.choices = [MagicMock()]
    empty_response.choices[0].message.tool_calls = None

    mock_groq.chat.completions.create.return_value = empty_response

    result = research_agent("topic")
    assert result is not None
    # Fallback ran
    assert mock_search.call_count == 1