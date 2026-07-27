import os

from config import _load_env
from langchain_core.tools import tool
from langchain_community.utilities import SerpAPIWrapper

_load_env()

OFFICIAL_DOMAINS = (
    "wikipedia.org", "docs.", "developer.", ".gov", ".edu",
    "github.com", "stackoverflow.com", "medium.com",
    "bbc.com", "reuters.com", "apnews.com", "techcrunch.com",
    "theverge.com", "wired.com", "forbes.com", "bloomberg.com",
    "nytimes.com", "theguardian.com", "cnn.com", "ndtv.com",
    "timesofindia.com", "hindustantimes.com"
)

serp_search = SerpAPIWrapper(
    serpapi_api_key=os.environ.get("SEARCH_API_KEY"),
    params={
        "engine": "google",
        "gl": "us",
        "hl": "en",
        "num": "10",
        "tbs": "qdr:d"  # past 24 hours for real-time results
    }
)


def _is_official(link: str) -> bool:
    return any(domain in link for domain in OFFICIAL_DOMAINS)


def _sort_by_official(items: list, link_key: str = "link") -> list:
    return sorted(
        items,
        key=lambda x: 0 if _is_official(x.get(link_key, "")) else 1
    )


@tool("web_tool")
def web_tool(query: str) -> str:
    """
    Search Google via SerpAPI for current and real-time information.
    Always prioritizes official and authoritative sources.
    """

    try:
        results = serp_search.results(query)
        output = []

        # 1. Answer Box
        answer_box = results.get("answer_box", {})
        if answer_box:
            answer = (
                answer_box.get("answer")
                or answer_box.get("snippet")
                or answer_box.get("result")
            )
            if answer:
                output.append(f"===== DIRECT ANSWER =====\n{answer}")

        # 2. Knowledge Graph
        kg = results.get("knowledge_graph", {})
        if kg:
            kg_parts = []
            if kg.get("title"):
                kg_parts.append(f"Title: {kg['title']}")
            if kg.get("description"):
                kg_parts.append(f"Description: {kg['description']}")
            if kg.get("source", {}).get("link"):
                kg_parts.append(f"Source: {kg['source']['link']}")
            if kg_parts:
                output.append("===== KNOWLEDGE GRAPH =====\n" + "\n".join(kg_parts))

        # 3. Latest News
        news = results.get("news_results", [])
        if news:
            news = _sort_by_official(news, "link")
            output.append("===== LIVE NEWS (Official Sources First) =====")
            for item in news[:5]:
                output.append(
                    f"Title: {item.get('title', '')}\n"
                    f"Date: {item.get('date', 'Unknown')}\n"
                    f"Source: {item.get('source', '')}\n"
                    f"Summary: {item.get('snippet', '')}\n"
                    f"Link: {item.get('link', '')}"
                )

        # 4. Organic Results
        organic = results.get("organic_results", [])
        if organic:
            organic = _sort_by_official(organic, "link")
            output.append("===== GOOGLE SEARCH RESULTS (Official Sources First) =====")
            for item in organic[:5]:
                output.append(
                    f"Title: {item.get('title', '')}\n"
                    f"Snippet: {item.get('snippet', '')}\n"
                    f"Date: {item.get('date', 'Unknown')}\n"
                    f"Link: {item.get('link', '')}"
                )

        if output:
            return "\n\n".join(output)

        return "No current information found."

    except Exception as e:
        print(f"[web_tool Error] {e}")
        return "Unable to retrieve current information."
