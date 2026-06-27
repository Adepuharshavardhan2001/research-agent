import logging
from app.tools import search_web, read_article
from app.report import generate_report
from app.memory import save_memory

logger = logging.getLogger(__name__)


def research_agent(topic: str) -> str:
    """Run the research agent workflow."""
    logger.info(f"Starting research on: {topic}")

    try:
        results = search_web(topic)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"Search failed for '{topic}': {e}"

    if not results:
        return f"No results found for '{topic}'."

    research = ""
    for item in results[:5]:
        try:
            article = read_article(item["url"])
            research += "\n\n" + article
        except Exception as e:
            logger.warning(f"Failed to read {item['url']}: {e}")
            research += f"\n[Failed to read: {item['url']}]"

    try:
        report = generate_report(topic, research)
        save_memory(topic, report)
        logger.info(f"Research completed: {topic}")
        return report
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return f"Research failed: {e}"