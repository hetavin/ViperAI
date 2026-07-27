import os
import json
import struct

from config import _load_env
from connect import db_connection

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from sentence_transformers import SentenceTransformer

_load_env()


# =====================================================
# LLM
# =====================================================

memory_llm = ChatGroq(
    model=os.environ["GROQ_MODEL"],
    api_key=os.environ["GROQ_API_KEY"],
    temperature=0
)


# =====================================================
# Embedding Model
# =====================================================

embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

memory_prompt = PromptTemplate.from_template("""
You are ViperAI's Long-Term Memory System.

Read ONLY the USER messages.

Extract facts that should remain useful for weeks or months.

Remember:

• Name
• Education
• Location
• Company
• Job
• Internship
• Skills
• Programming Languages
• Frameworks
• Current Projects
• Career Goals
• Learning Goals
• Preferences
• Devices
• Hobbies

Do NOT remember

- Greetings
- Temporary requests
- One-time bugs
- Error messages
- Random questions
- Assistant responses
- Passwords
- API Keys
- OTP
- Secrets

Each memory must contain

category
title
content

Allowed categories

personal
preferences
work
goals
health
finance
relationships
other

Return JSON only.

Conversation:

{conversation}

JSON:
""")

memory_chain = (
    memory_prompt
    | memory_llm
    | JsonOutputParser()
)

def embedding_to_blob(text: str):

    vector = embedding_model.encode(text)

    return struct.pack(
        f"{len(vector)}f",
        *vector
    )
    
# =====================================================
# Fetch Recent Messages
# =====================================================

def fetch_recent_messages(chat_id: int, limit: int = 20):

    conn = None
    cursor = None

    try:

        conn = db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                role,
                message
            FROM chat_messages
            WHERE chat_id = %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (chat_id, limit)
        )

        rows = cursor.fetchall()

        # Oldest → Newest
        rows.reverse()

        return rows

    except Exception as e:

        print(f"[Memory] Fetch Error: {e}")

        return []

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()
            
            
# =====================================================
# Format Conversation
# =====================================================

def format_conversation(rows):

    if not rows:
        return ""

    conversation = []

    for row in rows:

        if isinstance(row, dict):

            role = row["role"]
            message = row["message"]

        else:

            role = row[0]
            message = row[1]

        if role.lower() == "user":

            conversation.append(
                f"USER: {message}"
            )

        else:

            conversation.append(
                f"BOT: {message}"
            )

    return "\n".join(conversation)         


# =====================================================
# Extract Long-Term Memories
# =====================================================

def extract_memories(conversation: str):

    if not conversation.strip():

        return []

    try:

        result = memory_chain.invoke(
            {
                "conversation": conversation
            }
        )

        if isinstance(result, list):
            return result

        return []

    except Exception as e:

        print(f"[Memory] Extraction Error: {e}")

        return []
    
# =====================================================
# Save or Update Memory
# =====================================================

def save_memory(user_email: str, memory: dict):

    conn = None
    cursor = None

    try:

        category = memory.get(
            "category",
            "other"
        ).lower().strip()

        title = memory.get(
            "title",
            ""
        ).strip()

        content = memory.get(
            "content",
            ""
        ).strip()

        if not title or not content:
            return False

        valid_categories = {
            "personal",
            "preferences",
            "work",
            "goals",
            "health",
            "finance",
            "relationships",
            "other"
        }

        if category not in valid_categories:
            category = "other"

        embedding = embedding_to_blob(content)

        conn = db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                content
            FROM user_memories
            WHERE
                user_email=%s
                AND category=%s
                AND title=%s
            LIMIT 1
            """,
            (
                user_email,
                category,
                title
            )
        )

        existing = cursor.fetchone()

        # ----------------------------------------
        # Update Existing Memory
        # ----------------------------------------

        if existing:

            if isinstance(existing, dict):
                memory_id = existing["id"]
                old_content = existing["content"]
            else:
                memory_id = existing[0]
                old_content = existing[1]

            if old_content != content:

                cursor.execute(
                    """
                    UPDATE user_memories
                    SET
                        content=%s,
                        embedding=%s,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=%s
                    """,
                    (
                        content,
                        embedding,
                        memory_id
                    )
                )

                conn.commit()

                print(f"[Memory] Updated : {title}")

                return True

            return False

        # ----------------------------------------
        # Insert New Memory
        # ----------------------------------------

        cursor.execute(
            """
            INSERT INTO user_memories
            (
                user_email,
                category,
                title,
                content,
                embedding
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                user_email,
                category,
                title,
                content,
                embedding
            )
        )

        conn.commit()

        print(f"[Memory] Saved : {title}")

        return True

    except Exception as e:

        if conn:
            conn.rollback()

        print(f"[Memory] Save Error : {e}")

        return False

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()
            
            
# =====================================================
# Save All Memories
# =====================================================

def save_memories(
    user_email: str,
    memories: list
):

    if not memories:
        return 0

    saved = 0

    for memory in memories:

        try:

            if save_memory(
                user_email,
                memory
            ):
                saved += 1

        except Exception as e:

            print(e)

    return saved                               

# =====================================================
# Main Memory Pipeline
# =====================================================

def process_chat_memory(
    user_email: str,
    chat_id: int
):
    """
    Complete long-term memory pipeline.

    Steps
    -----
    1. Fetch recent messages
    2. Format conversation
    3. Extract memories using LLM
    4. Save / Update memories
    """

    try:

        print(
            f"[Memory] Processing chat {chat_id}"
        )

        rows = fetch_recent_messages(
            chat_id=chat_id,
            limit=20
        )

        if not rows:

            print(
                "[Memory] No messages found."
            )

            return

        conversation = format_conversation(
            rows
        )

        memories = extract_memories(
            conversation
        )

        if not memories:

            print(
                "[Memory] No memories extracted."
            )

            return

        saved = save_memories(
            user_email,
            memories
        )

        print(
            f"[Memory] Extracted : {len(memories)}"
        )

        print(
            f"[Memory] Saved/Updated : {saved}"
        )

    except Exception as e:

        print(
            f"[Memory] Pipeline Error : {e}"
        )