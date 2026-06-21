from app.tools import (
    search_web,
    read_article
)

from app.report import generate_report
from app.memory import save_memory


def research_agent(topic):

    # Search the web
    results = search_web(topic)

    research = ""

    # Read articles
    for item in results:

        url = item["url"]

        article = read_article(url)

        research += "\n\n" + article

    # Generate report
    report = generate_report(
        topic,
        research
    )

    # Save to memory
    save_memory(
        topic,
        report
    )

    return report