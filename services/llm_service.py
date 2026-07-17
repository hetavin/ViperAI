import logging
import re
import struct
from datetime import datetime
from typing import Literal, Optional

import requests as _requests
from ddgs import DDGS
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from config import Config
from connect import db_connection

# ── LLM instances ──────────────────────────────────────────────────────────────
_llm         = ChatGroq(api_key=Config.API_KEY, model=Config.MODEL, temperature=0.7, max_retries=2)
_llm_precise = ChatGroq(api_key=Config.API_KEY, model=Config.MODEL, temperature=0,   max_retries=2)
_llm_answer  = ChatGroq(api_key=Config.API_KEY, model=Config.MODEL, temperature=0.2, max_retries=2)

# ── Fast-router regexes ────────────────────────────────────────────────────────
_GREETING = re.compile(
    r'^\s*(hi|hello|hey|yo|sup|greetings|good\s*(morning|afternoon|evening|night)|'
    r'thanks|thank\s*you|bye|goodbye|'
    r'who\s+are\s+you|what\s+are\s+you|what\s+is\s+your\s+name|your\s+name)\s*[?!.]*\s*$',
    re.IGNORECASE
)
_MATH    = re.compile(r'^\s*[\d\s\+\-\*/\^\(\)\.%]+\s*$')
_DATETIME = re.compile(
    r'^\s*('
    r'what\s+(is\s+)?(the\s+)?(current\s+)?(date|time|day|year|month)'
    r'|what\s+time\s+is\s+it'
    r'|what.?s\s+(today.?s\s+)?(date|time|day|year)'
    r'|tell\s+(me\s+)?(the\s+)?(current\s+)?(time|date)'
    r'|(current|today.?s|now)\s*(date|time|day|year|month)?'
    r'|today.?s\s+(date|day)'
    r'|what\s+day\s+is\s+(it|today)'
    r'|date|time|today|now'
    r')\s*[?!.]*\s*$',
    re.IGNORECASE
)

# ── Pydantic models ────────────────────────────────────────────────────────────
class MemoryItem(BaseModel):
    id: Optional[int] = Field(None, description="Existing memory id, null if new")
    action: Literal["insert", "update", "delete"] = "insert"
    category: Literal["personal", "preferences", "work", "goals", "health", "finance", "relationships", "other"] = "other"
    title: str = Field(..., description="Short label for the memory")
    content: str = Field(..., description="The memory content")

class MemoryList(BaseModel):
    memories: list[MemoryItem]

class ResearchPlan(BaseModel):
    needs_search: bool = Field(..., description="True if the question requires current or external information")
    queries: list[str] = Field(default_factory=list, description="1–3 optimised search queries, empty if needs_search is false")

# ── Prompts ────────────────────────────────────────────────────────────────────
_SYSTEM_CORE = (
    "You are ViperAI, a fast, intelligent, accurate, and personalized AI assistant.\n"
    "Current date and time: {now_str}\n\n"
    "RULES:\n"
    "- Answer directly — no preamble, no 'As ViperAI...' phrases.\n"
    "- Never claim to be ChatGPT, GPT-4, Claude, Gemini, or any other AI.\n"
    "- Be concise by default; detailed when the question needs it.\n"
    "- If the user types an obvious year typo (e.g. '226' when current year is 2026), silently correct it.\n"
    "- For questions about recent or upcoming movies, shows, events, or news — rely on the search results provided; never use training data for current-year content.\n"
    "- When the user asks for information from an official source, use the URLs found in search results; never invent URLs.\n"
    "- Every URL must come verbatim from search results — never fabricate or shorten links.\n"
    "- Do not claim a partial search result set is exhaustive. If results may be incomplete, say so.\n"
    "- Do not fabricate facts. If current information cannot be verified from search results, clearly state the limitation.\n"
    "\nFORMATTING:\n"
    "- Choose the best structure for the question: prose, bullets, steps, table, code block, etc.\n"
    "- Use markdown headings and emojis only when they genuinely improve clarity.\n"
    "- For conversational questions, reply naturally without headers or bullets.\n"
    "- Always format links as [title](url) using only URLs from search results.\n"
    "- When search evidence is used, end your answer with a '## Sources' section listing each source as [title](url).\n"
)

_SYSTEM_PROMPT = PromptTemplate.from_template(_SYSTEM_CORE + "{memory_block}{search_block}")

_CHAT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "{system}"),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

_MEMORY_EXTRACT_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a memory consolidation assistant.\n"
     "RULES:\n"
     "- Save ONLY durable facts the user explicitly stated about themselves.\n"
     "- NEVER store: web-search findings, assistant responses, assumptions, temporary activities, or unverified inferences.\n"
     "- Merge duplicates, update outdated entries, delete irrelevant ones.\n"
     "{format_instructions}"),
    ("human",
     "Existing memories:\n{existing}\n\nNew conversation:\n{conv}\n\n"
     "Return only memories worth keeping long-term."),
])

_PLAN_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a search planning assistant. Today is {now_str}.\n"
     "Decide whether the question requires current or external information to answer accurately.\n"
     "needs_search = true for: current events, recent releases, live data, prices, people, places, "
     "official facts, anything that may have changed since your training cutoff.\n"
     "needs_search = false for: pure math, greetings, general coding help, timeless concepts.\n"
     "If needs_search is true, produce 1–3 short, specific, distinct search queries that together "
     "cover the information needed. Prefer queries that will surface authoritative sources.\n"
     "Return ONLY valid JSON matching the schema. No explanation.\n"
     "{format_instructions}"),
    ("human", "{question}"),
])

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — FAST ROUTER
# ══════════════════════════════════════════════════════════════════════════════
def _fast_route(q: str, now: datetime) -> Optional[str]:
    if _DATETIME.match(q):
        ql = q.lower()
        if any(w in ql for w in ['time', 'clock', 'now']) and not any(w in ql for w in ['date', 'day', 'year', 'month']):
            return f"The current time is **{now.strftime('%I:%M %p')}**."
        if 'year' in ql and not any(w in ql for w in ['date', 'time', 'day']):
            return f"The current year is **{now.strftime('%Y')}**."
        if 'day' in ql and not any(w in ql for w in ['date', 'time', 'year']):
            return f"Today is **{now.strftime('%A')}**."
        return f"Today is **{now.strftime('%A, %d %B %Y')}** and the current time is **{now.strftime('%I:%M %p')}**."
    return None

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2 — MEMORY RETRIEVAL
# ══════════════════════════════════════════════════════════════════════════════
def _cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na  = sum(x * x for x in a) ** 0.5
    nb  = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0

_MEMORY_THRESHOLD = 0.35

def _retrieve_memories(question: str, user_email: str, top_k: int = 6) -> list:
    try:
        conn = db_connection()
        if not conn:
            return []
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, category, title, content, embedding FROM user_memories WHERE user_email = %s",
                    (user_email,)
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        if not rows:
            return []

        from services.vector_service import get_model
        q_vec = get_model().encode(question).tolist()
        expected_dim = len(q_vec)

        scored = []
        for r in rows:
            raw = r.get("embedding")
            if not raw:
                continue
            if len(raw) % 4 != 0:
                logging.warning("Skipping memory id=%s: blob length %d not divisible by 4", r.get("id"), len(raw))
                continue
            n_floats = len(raw) // 4
            if n_floats != expected_dim:
                logging.warning("Skipping memory id=%s: dim mismatch (%d vs %d)", r.get("id"), n_floats, expected_dim)
                continue
            mem_vec = list(struct.unpack(f"{n_floats}f", raw))
            score = _cosine(q_vec, mem_vec)
            if score >= _MEMORY_THRESHOLD:
                scored.append((r, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored[:top_k]]
    except Exception:
        logging.exception("Memory retrieval failed (ignored)")
        return []

def _memory_block(memories: list) -> str:
    if not memories:
        return ""
    lines = ["\n--- RELEVANT USER MEMORY ---"]
    for m in memories:
        lines.append(f"[{m['category'].upper()}] {m['title']}: {m['content']}")
    lines.append("--- END MEMORY ---")
    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — RESEARCH PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
_GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
_GOOGLE_TIMEOUT    = 8

# ── 3a: Query planner ─────────────────────────────────────────────────────────
_plan_parser = PydanticOutputParser(pydantic_object=ResearchPlan)

def _plan_research(question: str, now_str: str) -> ResearchPlan:
    """Ask the LLM whether to search and what queries to run. Failure → search with raw question."""
    try:
        return (_PLAN_PROMPT | _llm_precise | _plan_parser).invoke({
            "now_str": now_str,
            "question": question,
            "format_instructions": _plan_parser.get_format_instructions(),
        })
    except Exception:
        logging.exception("Research planner failed — defaulting to search")
        return ResearchPlan(needs_search=True, queries=[question])

# ── 3b: Raw search providers ──────────────────────────────────────────────────
def _google_search_raw(query: str) -> list[dict]:
    """
    Returns list of {title, snippet, url} dicts from Google CSE.
    Raises on any failure so caller can fall back to DDGS.
    """
    api_key = Config.GOOGLE_SEARCH_API_KEY
    cx      = Config.GOOGLE_SEARCH_ENGINE_ID
    if not api_key or not cx:
        raise ValueError("Google Search credentials not configured")

    resp = _requests.get(
        _GOOGLE_SEARCH_URL,
        params={"key": api_key, "cx": cx, "q": query, "num": 10},
        timeout=_GOOGLE_TIMEOUT,
    )
    resp.raise_for_status()
    items = resp.json().get("items") or []
    if not items:
        raise ValueError("Google Search returned no results")

    return [
        {"title": it.get("title", ""), "snippet": it.get("snippet", ""), "url": it.get("link", "")}
        for it in items
    ]

def _ddgs_search_raw(query: str, max_results: int = 8) -> list[dict]:
    """Returns list of {title, snippet, url} dicts from DDGS. Never raises."""
    try:
        results = list(DDGS().text(query, max_results=max_results)) or []
        return [
            {"title": r.get("title", ""), "snippet": r.get("body", ""), "url": r.get("href", "")}
            for r in results
        ]
    except Exception:
        logging.exception("DDGS search failed for query: %r", query)
        return []

def _run_query(query: str) -> list[dict]:
    """Google first, DDGS fallback. Returns list of result dicts."""
    try:
        return _google_search_raw(query)
    except Exception as e:
        logging.warning("Google Search failed for %r — falling back to DDGS: %s", query, e)
        return _ddgs_search_raw(query)

# ── 3c: Dedup + rank ──────────────────────────────────────────────────────────
_AUTHORITATIVE_DOMAINS = {
    "wikipedia.org", "britannica.com", "reuters.com", "apnews.com",
    "bbc.com", "bbc.co.uk", "theguardian.com", "nytimes.com",
    "nature.com", "sciencedirect.com", "pubmed.ncbi.nlm.nih.gov",
    "gov", "edu", "ac.in", "ac.uk",
}

def _domain_score(url: str) -> int:
    """Return 1 if URL belongs to an authoritative domain, else 0."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower().lstrip("www.")
        return 1 if any(host.endswith(d) for d in _AUTHORITATIVE_DOMAINS) else 0
    except Exception:
        return 0

def _dedup_rank(all_results: list[dict], top_k: int = 10) -> list[dict]:
    """Deduplicate by URL, boost authoritative domains, return top_k."""
    seen_urls: set[str] = set()
    unique: list[dict]  = []
    for r in all_results:
        url = r.get("url", "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        r["_score"] = _domain_score(url)
        unique.append(r)
    unique.sort(key=lambda x: x["_score"], reverse=True)
    return unique[:top_k]

# ── 3d: Selective page scraping ───────────────────────────────────────────────
_SCRAPE_WORTHY_DOMAINS = {
    "wikipedia.org", "britannica.com", "gov", "edu", "ac.in", "ac.uk",
}
_MAX_SCRAPE_PAGES = 2
_SCRAPE_CHAR_LIMIT = 3000

def _should_scrape(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower().lstrip("www.")
        return any(host.endswith(d) for d in _SCRAPE_WORTHY_DOMAINS)
    except Exception:
        return False

def _scrape(url: str) -> str:
    try:
        from bs4 import BeautifulSoup
        resp = _requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        return " ".join(soup.get_text(separator=" ", strip=True).split())[:_SCRAPE_CHAR_LIMIT]
    except Exception as e:
        logging.warning("Scrape failed for %s: %s", url, e)
        return ""

# ── 3e: Main research entry point ─────────────────────────────────────────────
_MAX_SEARCH_BLOCK  = 10000
_MAX_SNIPPET_CHARS = 300

def _research(question: str, now_str: str) -> tuple[str, list[dict]]:
    """
    Run the full research pipeline.
    Returns (search_block_text, sources_list).
    sources_list = [{title, url}, ...] for the Sources section.
    """
    plan = _plan_research(question, now_str)

    if not plan.needs_search or not plan.queries:
        return "", []

    # Collect results for all queries
    all_results: list[dict] = []
    for query in plan.queries[:3]:
        all_results.extend(_run_query(query))

    ranked = _dedup_rank(all_results, top_k=10)
    if not ranked:
        return "", []

    # Selective scraping for authoritative pages
    scraped: dict[str, str] = {}
    scrape_count = 0
    for r in ranked:
        if scrape_count >= _MAX_SCRAPE_PAGES:
            break
        if _should_scrape(r["url"]):
            content = _scrape(r["url"])
            if content:
                scraped[r["url"]] = content
                scrape_count += 1

    # Build evidence block
    lines: list[str] = []
    total_chars = 0
    sources: list[dict] = []

    for i, r in enumerate(ranked, 1):
        title   = r.get("title", "")
        snippet = r.get("snippet", "")[:_MAX_SNIPPET_CHARS]
        url     = r.get("url", "")
        entry   = f"{i}. {title}\n   {snippet}\n   Source: {url}"

        if url in scraped:
            entry += f"\n   [Full content]: {scraped[url]}"

        if total_chars + len(entry) > _MAX_SEARCH_BLOCK:
            break

        lines.append(entry)
        total_chars += len(entry)
        if title and url:
            sources.append({"title": title, "url": url})

    search_block = (
        "\n--- SEARCH EVIDENCE ---\n"
        + "\n\n".join(lines)
        + "\n--- END EVIDENCE ---\n\n"
        "Use the evidence above to answer accurately. "
        "Cite sources using their exact URLs. Never invent or modify URLs. "
        "If evidence is incomplete for a broad request, say so."
    )
    return search_block, sources

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 4 — CONTEXT BUILDER
# ══════════════════════════════════════════════════════════════════════════════
_MAX_MEMORY_BLOCK  = 2000
_MAX_HISTORY_TURNS = 20

def _build_context(now_str: str, memories: list, history: list, search_block: str, file_contents) -> tuple[str, list]:
    mem_text = _memory_block(memories or [])
    if len(mem_text) > _MAX_MEMORY_BLOCK:
        mem_text = mem_text[:_MAX_MEMORY_BLOCK] + "\n...[memory truncated]"

    system_text = _SYSTEM_PROMPT.format(
        now_str=now_str,
        memory_block=mem_text,
        search_block=search_block,
    )
    lc_history = _to_lc_history((history or [])[-_MAX_HISTORY_TURNS:])
    return system_text, lc_history

def _to_lc_history(history):
    out = []
    for h in (history or []):
        out.append(HumanMessage(content=h["message"]) if h["role"] == "user" else AIMessage(content=h["message"]))
    return out

# ══════════════════════════════════════════════════════════════════════════════
# STAGE 5 — PRIMARY LLM  (temperature 0.2 when evidence present, else 0.7)
# ══════════════════════════════════════════════════════════════════════════════
_chain_answer  = ChatPromptTemplate.from_messages([
    ("system", "{system}"),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
]) | _llm_answer | StrOutputParser()

_chain_general = ChatPromptTemplate.from_messages([
    ("system", "{system}"),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
]) | _llm | StrOutputParser()

def _is_context_error(e: Exception) -> bool:
    s = str(e).lower()
    return any(w in s for w in ("context", "token", "length", "limit", "too long", "maximum"))

def _invoke_llm(system_text: str, lc_history: list, question: str, has_evidence: bool) -> str:
    chain = _chain_answer if has_evidence else _chain_general
    try:
        return chain.invoke({"system": system_text, "history": lc_history, "input": question})
    except Exception as e:
        if _is_context_error(e):
            logging.warning("Context overflow — retrying with reduced context")
            try:
                core_end = system_text.find("\n--- RELEVANT USER MEMORY ---")
                if core_end == -1:
                    core_end = system_text.find("\n--- SEARCH EVIDENCE ---")
                short_system = system_text[:core_end] if core_end > 0 else system_text[:5000]
                return chain.invoke({"system": short_system, "history": [], "input": question})
            except Exception:
                logging.exception("LLM retry also failed")
                return "I'm having trouble processing that right now. Please try rephrasing or try again shortly."
        logging.exception("Primary LLM call failed")
        return "I encountered an unexpected error. Please try again."

# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
def ask_llm(question, file_contents=None, memories=None, history=None, user_email=None):
    now     = datetime.now()
    now_str = now.strftime("%A, %d %B %Y %I:%M %p")
    q       = question.strip()

    # ── STAGE 1: Fast router ──────────────────────────────────────────────────
    if not file_contents:
        if _GREETING.match(q):
            memories = []
        elif _MATH.match(q):
            pass
        else:
            fast = _fast_route(q, now)
            if fast:
                return fast

    # ── STAGE 2: Memory retrieval ─────────────────────────────────────────────
    if user_email and memories is None:
        memories = _retrieve_memories(q, user_email)

    # ── STAGE 3: Research pipeline ────────────────────────────────────────────
    search_block = ""
    skip_research = bool(_GREETING.match(q) or _MATH.match(q)) or bool(file_contents)
    if not skip_research:
        search_block, _ = _research(q, now_str)

    has_evidence = bool(search_block)

    # ── STAGE 4: Context builder ──────────────────────────────────────────────
    if file_contents:
        system_text, _ = _build_context(now_str, memories, history, "", file_contents)
        parts = []
        for f in file_contents:
            if f["type"] == "text":
                parts.append({"type": "text", "text": f"[File: {f['name']}]\n{f['data']}"})
            elif f["type"] == "image":
                parts.append({"type": "image_url", "image_url": {"url": f"data:{f['mime']};base64,{f['data']}"}})
        parts.append({"type": "text", "text": question})
        try:
            return (_llm | StrOutputParser()).invoke(
                [SystemMessage(content=system_text), *_to_lc_history(history), HumanMessage(content=parts)]
            )
        except Exception:
            logging.exception("File LLM call failed")
            return "I encountered an error processing your file. Please try again."

    system_text, lc_history = _build_context(now_str, memories, history, search_block, None)

    # ── STAGE 5: Primary LLM ─────────────────────────────────────────────────
    return _invoke_llm(system_text, lc_history, question, has_evidence)


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY EXTRACTION  (called async after answer is sent)
# ══════════════════════════════════════════════════════════════════════════════
def extract_memories(history, existing_memories):
    conv = "\n".join(f"{h['role'].capitalize()}: {h['message']}" for h in history)
    existing = "\n".join(
        f"  [id:{m.get('id','?')}] [{m['category']}] {m['title']}: {m['content']}"
        for m in existing_memories
    ) if existing_memories else "None"

    parser = PydanticOutputParser(pydantic_object=MemoryList)
    try:
        result: MemoryList = (_MEMORY_EXTRACT_PROMPT | _llm_precise | parser).invoke({
            "existing": existing,
            "conv": conv,
            "format_instructions": parser.get_format_instructions(),
        })
        return [m.model_dump() for m in result.memories]
    except Exception:
        logging.exception("Memory extraction failed (ignored)")
        return []
