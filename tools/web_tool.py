import os
import re

from urllib.parse import urlparse

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

_BASE_PARAMS = {
    "engine": "google",
    "gl": "us",
    "hl": "en",
    "num": "10",
}

# Only news-shaped queries should be pinned to the last 24 hours. Applying it
# to everything starves documentation, comparison and how-to lookups.
_RECENCY_HINTS = re.compile(
    r"\b("
    r"today|tonight|now|current|currently|latest|newest|recent|recently|"
    r"news|breaking|live|score|scores|weather|forecast|price|stock|"
    r"this (?:week|month|morning|evening)|yesterday|just announced|"
    r"right now|so far"
    r")\b",
    re.IGNORECASE
)

serp_search = SerpAPIWrapper(
    serpapi_api_key=os.environ.get("SEARCH_API_KEY"),
    params=dict(_BASE_PARAMS)
)

serp_search_recent = SerpAPIWrapper(
    serpapi_api_key=os.environ.get("SEARCH_API_KEY"),
    params={**_BASE_PARAMS, "tbs": "qdr:d"}  # past 24 hours
)


def _needs_recency(query: str) -> bool:
    return bool(_RECENCY_HINTS.search(query or ""))


def _is_official(link: str) -> bool:
    host = (urlparse(link).hostname or "").lower()

    if host.startswith("www."):
        host = host[4:]

    if not host:
        return False

    for domain in OFFICIAL_DOMAINS:

        # "docs.", "developer." — subdomain prefixes
        if domain.endswith("."):
            if host.startswith(domain):
                return True

        # ".gov", ".edu" — TLD suffixes
        elif domain.startswith("."):
            if host.endswith(domain):
                return True

        # Registrable domain: match it or any of its subdomains, so that
        # evil.com/github.com no longer counts as official.
        elif host == domain or host.endswith("." + domain):
            return True

    return False


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
        engine = serp_search_recent if _needs_recency(query) else serp_search
        results = engine.results(query)
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
