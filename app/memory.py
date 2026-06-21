research_memory = []


def save_memory(topic, report):

    research_memory.append(
        {
            "topic": topic,
            "report": report
        }
    )


def get_memory():

    return research_memory


def get_last_memory():

    if research_memory:
        return research_memory[-1]

    return None


def clear_memory():

    research_memory.clear()