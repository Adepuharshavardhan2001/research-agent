import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY environment variable is not set")


def generate_report(topic: str, research: str) -> str:
    """Generate a structured research report using Groq LLM."""
    from groq import Groq

    if not research or not research.strip():
        return "Insufficient research data to generate report."

    if len(research) > 8000:
        research = research[:8000] + "..."

    prompt = f"""You are an expert research analyst.

Topic: {topic}

Research Data: {research}

Using the research data above, create a detailed research report.

Structure:
1. Executive Summary
2. Introduction
3. Key Findings
4. Detailed Analysis
5. Current Trends
6. Challenges
7. Future Scope
8. Conclusion

Write in a professional format. Use bullet points where necessary. Do not use markdown symbols."""

    try:
        logger.info(f"Generating report for: {topic}")
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        report = response.choices[0].message.content
        logger.info(f"Report generated: {len(report)} chars")
        return report
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise Exception(f"Failed to generate report: {e}")