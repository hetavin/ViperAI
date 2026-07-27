from connect import db_connection
from langchain_core.tools import tool


@tool("memory_tool")
def memory_tool(user_email: str, limit: int = 30) -> str:
    """
    Retrieve and format long-term memories for a user.
    """

    conn = None
    cursor = None

    try:
        conn = db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                category,
                title,
                content
            FROM user_memories
            WHERE user_email = %s
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (user_email, limit)
        )

        rows = cursor.fetchall()

        if not rows:
            return "No relevant long-term memories."

        grouped = {}
        seen = set()

        for row in rows:

            if isinstance(row, dict):
                category = row["category"]
                title = row["title"]
                content = row["content"]
            else:
                category = row[0]
                title = row[1]
                content = row[2]

            key = (category.lower(), title.lower(), content.lower())

            if key in seen:
                continue

            seen.add(key)

            if category not in grouped:
                grouped[category] = []

            grouped[category].append(f"- {title}: {content}")

        output = ["=== USER LONG-TERM MEMORY ==="]

        for category in ["personal", "preferences", "work", "goals",
                         "health", "finance", "relationships", "other"]:
            if category in grouped:
                output.append(f"\n[{category.upper()}]")
                output.extend(grouped[category])

        return "\n".join(output)

    except Exception as e:
        print(f"[Memory Tool Error] {e}")
        return "Unable to retrieve user memories."

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
