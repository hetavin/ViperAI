import os

from config import _load_env
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from tools import web_tool, memory_tool


# ==================================================
# LOAD ENVIRONMENT VARIABLES
# ==================================================

_load_env()


# ==================================================
# 1. LLM
# ==================================================

llm = ChatGroq(
    model=os.environ.get("GROQ_MODEL"),
    api_key=os.environ.get("GROQ_API_KEY"),
    temperature=0
)

parser = StrOutputParser()


# ==================================================
# 2. FORMAT CONVERSATION HISTORY
# ==================================================

def format_conversation_history(history: list) -> str:

    if not history:
        return "No recent conversation history."

    formatted = []

    for item in history:

        if isinstance(item, dict):
            role = item.get("role", "unknown")
            message = item.get("message", "")
        else:
            role = item[0]
            message = item[1]

        if role == "user":
            role_name = "USER"
        elif role == "bot":
            role_name = "ASSISTANT"
        else:
            role_name = role.upper()

        formatted.append(f"{role_name}: {message}")

    return "\n".join(formatted)


# ==================================================
# 3. QUERY CLASSIFIER
# ==================================================

classifier_prompt = PromptTemplate.from_template("""
You are a query classifier for ViperAI.

Classify the CURRENT USER QUERY into EXACTLY ONE of these 7 categories:

GENERAL
  - Timeless knowledge: concepts, coding, math, science, history, how-things-work.
  - No live data needed. No personal user info needed.
  - Examples: "What is recursion?", "Write a Python function", "Explain TCP/IP", "How does JWT work?"

WEB
  - Requires live / real-time / current data from the internet.
  - No personal user info needed.
  - Examples: "Latest iPhone price", "Today's weather", "Current Bitcoin price", "Who won the match today?"

MEMORY
  - User asking about THEIR OWN stored info: name, skills, projects, goals, preferences, job.
  - No live data needed. No general explanation needed.
  - Examples: "What are my skills?", "What am I working on?", "Tell me about myself", "What's my goal?"

GENERAL_MEMORY
  - User wants technical help, code, explanation, or advice — AND their personal context (stack, project, language, framework) makes the answer more useful.
  - No live data needed.
  - Examples:
    "How do I add authentication to my project?"
    "Help me structure my Flask app"
    "Write a login API for my app"
    "How should I handle errors in my project?"
    "Explain how to use the framework I'm learning"
    "What should I learn next?"
    "Suggest a project for me"
    "Am I ready for a job interview?"
    "How do I improve my Python skills?"
    "Best way to build the feature I'm working on"

WEB_MEMORY
  - Personalized + live data both needed.
  - Examples: "Find internships matching my skills", "What jobs suit me right now?", "Latest courses for my stack", "Best libraries for my current project?"

WEB_GENERAL
  - Live data + general reasoning needed. No personal user info.
  - Examples: "Compare latest AI models", "Best Python frameworks in 2025", "Is React still popular?", "Latest version of Django?"

WEB_GENERAL_MEMORY
  - All three: live data + general knowledge + user profile.
  - Examples: "Build a learning roadmap for me", "What AI projects should I build based on my skills?", "Latest tools I should add to my stack?"

Decision Rules (apply in order):
1. Does it need LIVE / CURRENT / REAL-TIME data? → must include WEB
2. Does it ask for technical help (code, explanation, how-to) where knowing the user's stack, project, language, or framework would make the answer more relevant and personalized? → must include MEMORY + GENERAL
3. Does it reference the USER personally (my skills, my projects, my goals, about me) without needing technical explanation? → MEMORY only
4. Does it need general explanation or reasoning with no personal context? → GENERAL only
5. Apply only the flags that are truly needed — do not over-classify.

Return EXACTLY ONE category. No explanation. No punctuation. No extra text.

Recent Conversation History (for context only):
{conversation_history}

Current User Query:
{query}

Classification:
""")

classifier_chain = classifier_prompt | llm | parser


# ==================================================
# 4. ANSWER PROMPT
# ==================================================

answer_prompt = PromptTemplate.from_template("""
You are ViperAI, a personal AI assistant created by Hetavin Pokiya.

Question: {query}

Conversation History:
{conversation_history}

User Profile:
{memories}

Web Results:
{web_results}

Rules:
- Answer directly. No filler, no preamble, no "Great question!".
- Use User Profile to personalize — tailor code, advice, and examples to the user's stack, projects, and goals. Never give generic answers when you know their context.
- Use Web Results only for current/live facts. Cite the source link inline.
- If Web Results say "Not required" — ignore them completely.
- If User Profile says "No memories" — answer without personalization.
- Never mention memory, tools, query type, or any system internals.
- Use code blocks, bullet points, or headers only when they genuinely help.
- Be concise. Say exactly what's needed, nothing more.

Answer:
""")

answer_chain = answer_prompt | llm | parser


# ==================================================
# 5. VALID QUERY TYPES
# ==================================================

VALID_TYPES = {
    "GENERAL", "WEB", "MEMORY",
    "GENERAL_MEMORY", "WEB_MEMORY",
    "WEB_GENERAL", "WEB_GENERAL_MEMORY"
}


# ==================================================
# 6. MAIN CHAT FUNCTION
# ==================================================

def chat(
    query: str,
    user_email: str,
    history: list
) -> str:

    conversation_history = format_conversation_history(history)

    try:
        query_type = classifier_chain.invoke({
            "query": query,
            "conversation_history": conversation_history
        }).strip().upper()

        if query_type not in VALID_TYPES:
            query_type = "GENERAL"

    except Exception as e:
        print(f"[Classifier Error] {e}")
        query_type = "GENERAL"

    print(f"[ViperAI] Query Type: {query_type}")

    need_web    = "WEB"    in query_type
    need_memory = "MEMORY" in query_type

    web_results = web_tool.invoke({"query": query}) if need_web else "Not required."
    memories    = memory_tool.invoke({"user_email": user_email}) if need_memory else "No memories loaded for this query."

    return answer_chain.invoke({
        "query":                query,
        "conversation_history": conversation_history,
        "memories":             memories,
        "web_results":          web_results
    })
