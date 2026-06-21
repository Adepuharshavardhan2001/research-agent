from dotenv import load_dotenv
from groq import Groq
import os

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


def generate_report(topic, research):

    prompt = f"""
You are an expert research analyst.

Topic:
{topic}

Research Data:
{research}

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

Write in a professional format.
Use bullet points where necessary.
Do not use markdown symbols.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
        max_tokens=2000
    )

    return response.choices[0].message.content