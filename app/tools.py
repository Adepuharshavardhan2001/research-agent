import os
import requests

from bs4 import BeautifulSoup
from tavily import TavilyClient


tavily = TavilyClient(
    api_key=os.getenv(
        "TAVILY_API_KEY"
    )
)



def search_web(query):

    result = tavily.search(
        query=query,
        max_results=3
    )

    return result["results"]



def read_article(url):

    html = requests.get(url).text


    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    text = soup.get_text()

    return text[:2000]