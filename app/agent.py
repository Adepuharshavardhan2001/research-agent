import json
import structlog
from groq import Groq

from app.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_TEMPERATURE,
    GROQ_TIMEOUT_SECONDS,
    AGENT_MAX_STEPS,
    AGENT_MAX_LLM_RETRIES,
)
from app.schemas import AgentState, AgentDecision, Finding
from app.tools import search_web, read_article, TOOLS_SPEC
from app.report import generate_report

logger = structlog.get_logger()

groq_client = Groq(api_key=GROQ_API_KEY)


# ============================================================
# LLM decision: "what should I do next?"
# ============================================================

SYSTEM_PROMPT = """You are an autonomous research agent.

Your goal: research the user's topic thoroughly and gather enough evidence to write a comprehensive report.

You have three possible actions each step:
1. search_web — search the web for information
2. read_article — read a specific URL to extract its content
3. finish — stop researching and write the report

Workflow rules (IMPORTANT — follow these strictly):
- Step 1: search_web ONCE to find sources.
- Steps 2+: DO NOT search again unless the results were useless. Instead, READ articles.
- You must READ AT LEAST 2 ARTICLES before you finish. Search snippets are not enough.
- NEVER repeat a query you already tried. The list of tried queries is given to you.
- NEVER read a URL you already read. The list of read URLs is given to you.
- If you have already searched twice and read 2+ articles, call finish.
- If steps_remaining <= 2, call finish NOW.

Decision priority:
1. If you have not searched yet → search_web
2. If you have search results but haven't read enough → read_article (pick the most authoritative URL from the UNREAD list)
3. If you have read 2+ articles → finish
4. If steps_remaining <= 2 → finish
"""


def _build_state_summary(state: AgentState) -> str:
    """Compact summary of what the agent has done so far."""
    steps_remaining = state.max_steps - state.step
    articles_read = sum(1 for f in state.findings if f.type == "article")
    searches_done = sum(1 for f in state.findings if f.type == "search")

    lines = [
        f"Topic: {state.topic}",
        f"Step: {state.step} / {state.max_steps}  (steps_remaining: {steps_remaining})",
        f"Searches completed: {searches_done}",
        f"Articles read: {articles_read}",
        f"Queries already tried (DO NOT repeat): {state.queries_tried}",
        f"URLs already read (DO NOT repeat): {list(state.urls_seen)}",
        "",
    ]

    if steps_remaining <= 2:
        lines.append(">>> WARNING: steps_remaining <= 2. You MUST call finish now. <<<")
        lines.append("")

    if not state.findings:
        lines.append("(no findings yet — you must search first)")
    else:
        lines.append("Findings so far:")
        for i, f in enumerate(state.findings, 1):
            if f.type == "search":
                count = len(f.data) if isinstance(f.data, list) else 0
                lines.append(f"  [{i}] SEARCH returned {count} results")
                if isinstance(f.data, list):
                    for r in f.data[:3]:
                        url = r.get("url") if isinstance(r, dict) else None
                        title = r.get("title") if isinstance(r, dict) else None
                        if url and url not in state.urls_seen:
                            lines.append(f"       → UNREAD: {title} :: {url}")
            elif f.type == "article":
                preview = (f.data or "")[:200].replace("\n", " ")
                lines.append(f"  [{i}] ARTICLE (first 200 chars): {preview}...")

    return "\n".join(lines)


def _llm_decide_next_action(state: AgentState) -> AgentDecision | None:
    """
    Ask the LLM for the next action.
    Returns AgentDecision on success, None if the LLM fails repeatedly.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_state_summary(state)},
    ]

    for attempt in range(1, AGENT_MAX_LLM_RETRIES + 1):
        try:
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                tools=TOOLS_SPEC,
                tool_choice="auto",
                temperature=GROQ_TEMPERATURE,
                timeout=GROQ_TIMEOUT_SECONDS,
            )

            choice = response.choices[0].message

            if not choice.tool_calls:
                return AgentDecision(action="finish", reasoning="LLM returned no tool call")

            tool_call = choice.tool_calls[0]
            name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            logger.info(
                "llm_decision",
                step=state.step,
                tool=name,
                args=args,
                attempt=attempt,
            )

            if name == "search_web":
                return AgentDecision(action="search", query=args.get("query"))
            elif name == "read_article":
                return AgentDecision(action="read", url=args.get("url"))
            elif name == "finish":
                return AgentDecision(
                    action="finish",
                    reasoning=args.get("reasoning", "LLM chose to finish"),
                )
            else:
                return AgentDecision(action="finish", reasoning=f"Unknown tool {name}")

        except Exception as e:
            logger.warning("llm_decision_failed", attempt=attempt, error=str(e))

    logger.error("llm_decision_exhausted_retries", step=state.step)
    return None


# ============================================================
# Tool executors
# ============================================================

def _execute_search(state: AgentState, query: str) -> None:
    if not query or query in state.queries_tried:
        logger.info("search_skipped_duplicate", query=query)
        return

    result = search_web(query)
    state.queries_tried.append(query)

    if result.success:
        state.findings.append(
            Finding(type="search", data=[r.model_dump() for r in result.results], step=state.step)
        )
        logger.info("agent_search", query=query, count=len(result.results))
    else:
        logger.warning("agent_search_failed", query=query, error=result.error)


def _execute_read(state: AgentState, url: str) -> None:
    if not url or url in state.urls_seen:
        logger.info("read_skipped_duplicate", url=url)
        return

    result = read_article(url)
    state.urls_seen.add(url)

    if result.success:
        state.findings.append(
            Finding(type="article", data=result.text, step=state.step)
        )
        logger.info("agent_read", url=url, length=len(result.text))
    else:
        logger.warning("agent_read_failed", url=url, error=result.error)


def _first_unread_url(state: AgentState) -> str | None:
    """Return the first URL from search findings not yet read."""
    for f in state.findings:
        if f.type == "search" and isinstance(f.data, list):
            for r in f.data:
                url = r.get("url") if isinstance(r, dict) else None
                if url and url not in state.urls_seen:
                    return url
    return None


# ============================================================
# Fallback pipeline (if the LLM can't decide)
# ============================================================

def _fallback_pipeline(topic: str) -> str:
    """Simple linear pipeline — used if the agent loop fails."""
    logger.warning("agent_fallback_pipeline", topic=topic)

    state = AgentState(topic=topic, max_steps=1)
    _execute_search(state, topic)

    for finding in state.findings:
        if finding.type == "search":
            for r in finding.data[:2]:
                _execute_read(state, r["url"])

    return generate_report(state)


# ============================================================
# The agent loop
# ============================================================

def research_agent(topic: str) -> str:
    """
    Agentic research: the LLM decides each step.
    Returns a final report.
    """
    logger.info("agent_started", topic=topic, max_steps=AGENT_MAX_STEPS)

    state = AgentState(topic=topic, max_steps=AGENT_MAX_STEPS)

    while state.step < state.max_steps:
        state.step += 1

        steps_remaining = state.max_steps - state.step

        if steps_remaining <= 0:
            logger.info("agent_max_steps_reached", step=state.step)
            break

        decision = _llm_decide_next_action(state)

        if decision is None:
            logger.warning("agent_decision_failed", step=state.step)
            break

        if decision.action == "finish":
            logger.info("agent_finished", step=state.step, reason=decision.reasoning)
            state.finished = True
            break

        elif decision.action == "search":
            searches_done = sum(1 for f in state.findings if f.type == "search")

            # Guardrail: if the LLM tries to repeat a search after 2 searches, force a read
            if searches_done >= 2 and decision.query in state.queries_tried:
                unread = _first_unread_url(state)
                if unread:
                    logger.info(
                        "agent_forced_read",
                        reason="repeated_search_refused",
                        step=state.step,
                    )
                    _execute_read(state, unread)
                else:
                    logger.info("agent_no_unread_urls", step=state.step)
            else:
                _execute_search(state, decision.query or "")

        elif decision.action == "read":
            _execute_read(state, decision.url or "")

    if not state.findings:
        return _fallback_pipeline(topic)

    logger.info(
        "agent_complete",
        topic=topic,
        steps=state.step,
        findings=len(state.findings),
        articles_read=sum(1 for f in state.findings if f.type == "article"),
        searches_done=sum(1 for f in state.findings if f.type == "search"),
    )

    return generate_report(state)