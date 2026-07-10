import requests
import base64
import json
from config import Config


def ask_llm(question, file_contents=None, memories=None, history=None):
    headers = {
        "Authorization": f"Bearer {Config.API_KEY}",
        "Content-Type": "application/json"
    }

    # ── System prompt ────────────────────────────────────────────────────────
    system_parts = [
        "You are ViperAI. Follow these rules strictly:",
        "1. NEVER introduce yourself or mention what you can do unless the user explicitly asks (e.g. 'who are you', 'what are you', 'what can you do').",
        "2. For all other questions, answer directly — no preamble, no self-introduction, no 'As ViperAI...' phrases.",
        "3. Never claim to be ChatGPT, GPT-4, Claude, Gemini, or any other AI.",
        "4. Be concise and direct.",
        "5. Use the user's memory and conversation history below to give personalised, context-aware answers.",
    ]

    if memories:
        system_parts.append("\n--- USER MEMORY ---")
        from itertools import groupby
        memories_sorted = sorted(memories, key=lambda m: m["category"])
        for cat, items in groupby(memories_sorted, key=lambda m: m["category"]):
            system_parts.append(f"[{cat.upper()}]")
            for m in items:
                system_parts.append(f"  - {m['title']}: {m['content']}")
        system_parts.append("--- END MEMORY ---")

    system_content = "\n".join(system_parts)

    # ── Build messages list ───────────────────────────────────────────────────
    messages = [{"role": "system", "content": system_content}]

    # Inject last N history messages as proper conversation turns
    if history:
        for h in history:
            role = "assistant" if h["role"] == "bot" else "user"
            messages.append({"role": role, "content": h["message"]})

    # ── Current user message (with optional files) ────────────────────────────
    content = []
    if file_contents:
        for f in file_contents:
            if f["type"] == "text":
                content.append({"type": "text", "text": f"[File: {f['name']}]\n{f['data']}"})
            elif f["type"] == "image":
                content.append({"type": "image_url", "image_url": {"url": f"data:{f['mime']};base64,{f['data']}"}})
    content.append({"type": "text", "text": question})
    messages.append({"role": "user", "content": content})

    payload = {"model": Config.MODEL, "messages": messages}

    try:
        response = requests.post(
            f"{Config.API_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {e}"


def extract_memories(history, existing_memories):
    """
    Send full conversation history + existing memories to LLM.
    LLM first reads existing memories, then decides: insert / update / delete.
    Returns list of dicts: [{action, category, title, content}, ...]
    """
    headers = {
        "Authorization": f"Bearer {Config.API_KEY}",
        "Content-Type": "application/json"
    }

    conv = "\n".join(
        f"{h['role'].capitalize()}: {h['message']}" for h in history
    )

    existing = "\n".join(
        f"  [id:{m.get('id','?')}] [{m['category']}] {m['title']}: {m['content']}"
        for m in existing_memories
    ) if existing_memories else "None"

    prompt = f"""You are a memory manager for an AI assistant. Your job is to keep the user's memory table accurate, consolidated and up-to-date.

## STEP 1 — Read existing memories carefully:
{existing}

## STEP 2 — Read the full conversation:
{conv}

## STEP 3 — Decide what to do:
Rules:
- CONSOLIDATE: If multiple existing memories say the same thing in different ways, merge them into one clean "update" and "delete" the redundant ones.
- UPDATE: If new info from conversation changes or extends an existing memory, update that memory with the full consolidated content. Do NOT keep the old version.
- INSERT: Only if the fact is completely new and not covered by any existing memory.
- DELETE: If an existing memory is now outdated, redundant, or contradicted.
- NEVER duplicate. If similar info already exists, update it — do not insert a new one.
- Write content as a single clean sentence. Combine related facts into one memory where it makes sense.
- Categories: personal, preferences, work, goals, health, finance, relationships, other
- title should be short and reusable (e.g. "Full name", "Projects built", "Career goal", "City")

## Example:
Existing memories:
  [personal] Full name: Hetavin
  [work] Project: Build ViperAI
  [work] Project: Build Edusync
  [personal] Identity: Hetavin is the creator of ViperAI

After analysis the correct output should be:
[
  {{"action": "update", "category": "personal", "title": "Full name", "content": "User's name is Hetavin Pokiya"}},
  {{"action": "update", "category": "work", "title": "Projects built", "content": "Hetavin built EduSync and is currently building ViperAI using Python"}},
  {{"action": "delete", "category": "work", "title": "Project", "content": ""}},
  {{"action": "delete", "category": "personal", "title": "Identity", "content": ""}},
  {{"action": "update", "category": "goals", "title": "Career goal", "content": "Hetavin wants to become an AI engineer"}}
]

Now output the JSON array for the actual memories and conversation above. Respond ONLY with valid JSON, no explanation."""

    payload = {
        "model": Config.MODEL,
        "messages": [
            {"role": "system", "content": "You are a memory consolidation assistant. Always read existing memories first, then consolidate and update. Output only valid JSON array."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0
    }
    try:
        response = requests.post(
            f"{Config.API_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception:
        return []