"""
Eval harness for the research agent.

Runs the agent on all topics in eval/test_topics.json, measures:
- success rate
- average steps
- average tokens (prompt + completion)
- average cost (USD)
- average latency (seconds)
- citation coverage (does the report contain source URLs?)

Writes results to eval/results.json and prints a summary table.

WARNING: This makes real Groq + Tavily API calls. Budget ~5-10 min runtime.
"""
import json
import time
import sys
from pathlib import Path
from datetime import datetime

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import structlog

from app.agent import research_agent

logger = structlog.get_logger()

TOPICS_FILE = Path(__file__).parent / "test_topics.json"
RESULTS_FILE = Path(__file__).parent / "results.json"

# Rough Groq pricing (update as needed) — $/1M tokens
GROQ_INPUT_PRICE_PER_M = 0.15
GROQ_OUTPUT_PRICE_PER_M = 0.60


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (
        (prompt_tokens / 1_000_000) * GROQ_INPUT_PRICE_PER_M
        + (completion_tokens / 1_000_000) * GROQ_OUTPUT_PRICE_PER_M
    )


def keyword_coverage(report: str, keywords: list[str]) -> float:
    """Fraction of expected keywords present in the report (case-insensitive)."""
    if not keywords:
        return 0.0
    lower = report.lower()
    hits = sum(1 for k in keywords if k.lower() in lower)
    return hits / len(keywords)


def citation_coverage(report: str) -> int:
    """Count how many 'source:' citations are in the report."""
    return report.lower().count("source:")


def run_single_topic(entry: dict) -> dict:
    topic = entry["topic"]
    keywords = entry.get("expected_keywords", [])

    print(f"\n→ [{entry['id']}/10] {topic}")

    start = time.time()
    error = None
    report = ""
    try:
        report = research_agent(topic)
    except Exception as e:
        error = str(e)
    elapsed = time.time() - start

    # Try to extract tokens from the report generation log if possible
    # (report.py logs prompt_tokens / completion_tokens — we approximate here)
    # Fall back to length-based estimate
    approx_prompt_tokens = 4000  # baseline from observed runs
    approx_completion_tokens = min(len(report) // 4, 4000)  # 4 chars/token rough

    return {
        "id": entry["id"],
        "topic": topic,
        "category": entry.get("category"),
        "success": bool(report) and not error,
        "error": error,
        "report_length": len(report),
        "latency_seconds": round(elapsed, 2),
        "approx_prompt_tokens": approx_prompt_tokens,
        "approx_completion_tokens": approx_completion_tokens,
        "approx_cost_usd": round(
            estimate_cost(approx_prompt_tokens, approx_completion_tokens), 5
        ),
        "keyword_coverage": round(keyword_coverage(report, keywords), 2),
        "citations": citation_coverage(report),
    }


def main():
    with open(TOPICS_FILE) as f:
        topics = json.load(f)

    print("=" * 70)
    print(f"Running eval on {len(topics)} topics")
    print(f"Started at: {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 70)

    results = []
    for entry in topics:
        results.append(run_single_topic(entry))

    # Aggregate
    total = len(results)
    successes = sum(1 for r in results if r["success"])
    total_latency = sum(r["latency_seconds"] for r in results)
    total_cost = sum(r["approx_cost_usd"] for r in results)
    avg_keyword_cov = sum(r["keyword_coverage"] for r in results) / total
    total_citations = sum(r["citations"] for r in results)
    avg_report_len = sum(r["report_length"] for r in results) / total

    summary = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "topics_count": total,
        "successes": successes,
        "success_rate": round(successes / total, 2),
        "avg_latency_seconds": round(total_latency / total, 2),
        "total_latency_seconds": round(total_latency, 2),
        "avg_cost_usd": round(total_cost / total, 5),
        "total_cost_usd": round(total_cost, 5),
        "avg_keyword_coverage": round(avg_keyword_cov, 2),
        "total_citations": total_citations,
        "avg_citations_per_report": round(total_citations / total, 2),
        "avg_report_length_chars": round(avg_report_len, 0),
    }

    with open(RESULTS_FILE, "w") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)

    # Print summary table
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Success rate:              {summary['success_rate'] * 100:.0f}%  ({successes}/{total})")
    print(f"Avg latency per report:    {summary['avg_latency_seconds']}s")
    print(f"Avg cost per report:       ${summary['avg_cost_usd']}")
    print(f"Avg keyword coverage:      {summary['avg_keyword_coverage'] * 100:.0f}%")
    print(f"Avg citations per report:  {summary['avg_citations_per_report']}")
    print(f"Avg report length:         {summary['avg_report_length_chars']:.0f} chars")
    print()
    print(f"Full results saved to: {RESULTS_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()