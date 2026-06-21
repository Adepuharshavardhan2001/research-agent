from app.celery_worker import celery
from app.agent import research_agent


@celery.task
def run_research(topic):

    print(f"TOPIC: {topic}")

    result = research_agent(topic)

    print("REPORT GENERATED")

    return result