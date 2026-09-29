import structlog
from groq import Groq

from app.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_MAX_TOKENS,
    GROQ_TIMEOUT_SECONDS,
)
from app.schemas import AgentState

logger = structlog.get_logger()

groq_client = Groq(api_key=GROQ_API_KEY)


REPORT_PROMPT = """You are a research analyst.

Write a comprehensive, well-structured report based ONLY on the research data provided below.

Topic:
{topic}

Research data collected by the agent:
{research}

Instructions:
1. Only use information present in the research data above. Do not invent facts.
2. Every key claim must include a citation in the format (source: <url>).
3. Use this structure:
   1. Executive Summary
   2. Introduction
   3. Key Findings
   4. Detailed Analysis
   5. Current Trends
   6. Challenges
   7. Future Scope
   8. Conclusion
4. If the research data does not contain enough information for a section, write "Insufficient data" — do NOT make things up.
5. Write in professional English. Use bullet points where helpful. Do not use markdown symbols.
"""


def _format_findings(state: AgentState) -> str:
    """Turn agent findings into a single string for the LLM."""
    parts = []
    for i, finding in enumerate(state.findings, 1):
        if finding.type == "search":
            for r in finding.data:
                parts.append(
                    f"[Search result {i}]\nTitle: {r.get('title')}\nURL: {r.get('url')}\n"
                    f"Snippet: {r.get('snippet')}\n"
                )
        elif finding.type == "article":
            parts.append(f"[Article {i}]\n{finding.data}\n")

    combined = "\n\n".join(parts)

    # Cap total length to avoid blowing Groq context
    MAX_RESEARCH_CHARS = 30000
    if len(combined) > MAX_RESEARCH_CHARS:
        combined = combined[:MAX_RESEARCH_CHARS] + "\n\n[research truncated]"

    return combined


def generate_report(state: AgentState) -> str:
    """
    Generate a cited, grounded report from agent findings.
    Returns the report text.
    """
    if not state.findings:
        return "Insufficient data: the agent did not collect any findings."

    research_text = _format_findings(state)

    prompt = REPORT_PROMPT.format(topic=state.topic, research=research_text)

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=GROQ_MAX_TOKENS,
            timeout=GROQ_TIMEOUT_SECONDS,
        )

        report = response.choices[0].message.content

        usage = response.usage
        logger.info(
            "report_generated",
            topic=state.topic,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            report_length=len(report) if report else 0,
        )

        if not report or len(report) < 200:
            logger.warning("report_too_short", topic=state.topic)
            return "Insufficient data to produce a reliable report."

        return report

    except Exception as e:
        logger.error("report_generation_failed", topic=state.topic, error=str(e))
        return f"Report generation failed: {e}"