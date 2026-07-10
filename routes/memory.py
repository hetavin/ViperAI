from flask import Blueprint, request, jsonify, session
from threading import Thread
from connect import db_connection
from services.vector_service import save_memory_embedding

memory_bp = Blueprint("memory", __name__)

VALID_CATEGORIES = {'personal', 'preferences', 'work', 'goals', 'health', 'finance', 'relationships', 'other'}


def update_user_memories(user_email, memories):
    """
    Upserts/deletes memories based on LLM actions: insert / update / delete.
    """
    if not memories or not user_email:
        return
    conn = db_connection()
    if not conn:
        return
    try:
        for m in memories:
            action   = m.get("action", "insert")
            category = m.get("category", "other")
            title    = (m.get("title") or "").strip()[:255]
            content  = (m.get("content") or "").strip()
            if not title or category not in VALID_CATEGORIES:
                continue

            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM user_memories WHERE user_email=%s AND category=%s AND title=%s",
                    (user_email, category, title)
                )
                row = cur.fetchone()

                if action == "delete":
                    if row:
                        cur.execute("DELETE FROM user_memories WHERE id=%s", (row["id"],))
                    conn.commit()
                    continue

                if action == "update" and row:
                    cur.execute(
                        "UPDATE user_memories SET content=%s, embedding=NULL, updated_at=NOW() WHERE id=%s",
                        (content, row["id"])
                    )
                    memory_id = row["id"]
                else:
                    # insert (or upsert if title already exists)
                    if row:
                        cur.execute(
                            "UPDATE user_memories SET content=%s, embedding=NULL, updated_at=NOW() WHERE id=%s",
                            (content, row["id"])
                        )
                        memory_id = row["id"]
                    else:
                        cur.execute(
                            "INSERT INTO user_memories (user_email, category, title, content) VALUES (%s,%s,%s,%s)",
                            (user_email, category, title, content)
                        )
                        memory_id = cur.lastrowid

            conn.commit()
            save_memory_embedding(memory_id, content)
    except Exception as e:
        print(f"Memory update error: {e}")
    finally:
        conn.close()

@memory_bp.route("/api/memory", methods=["POST"])
def add_memory():
    if "user_email" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    category = data.get("category", "other")
    title    = (data.get("title") or "").strip()
    content  = (data.get("content") or "").strip()

    if not title or not content:
        return jsonify({"error": "title and content are required"}), 400
    if category not in VALID_CATEGORIES:
        return jsonify({"error": "Invalid category"}), 400

    conn = db_connection()
    if not conn:
        return jsonify({"error": "DB error"}), 500
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_memories (user_email, category, title, content) VALUES (%s, %s, %s, %s)",
                (session["user_email"], category, title, content)
            )
            memory_id = cur.lastrowid
        conn.commit()
        Thread(target=save_memory_embedding, args=(memory_id, content), daemon=True).start()
        return jsonify({"ok": True, "id": memory_id}), 201
    finally:
        conn.close()


@memory_bp.route("/api/memory", methods=["GET"])
def get_memories():
    if "user_email" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    category = request.args.get("category")
    conn = db_connection()
    if not conn:
        return jsonify({"error": "DB error"}), 500
    try:
        with conn.cursor() as cur:
            if category and category in VALID_CATEGORIES:
                cur.execute(
                    "SELECT id, category, title, content, created_at FROM user_memories WHERE user_email = %s AND category = %s ORDER BY created_at DESC",
                    (session["user_email"], category)
                )
            else:
                cur.execute(
                    "SELECT id, category, title, content, created_at FROM user_memories WHERE user_email = %s ORDER BY category, created_at DESC",
                    (session["user_email"],)
                )
            rows = cur.fetchall()
        return jsonify({"memories": [
            {"id": r["id"], "category": r["category"], "title": r["title"],
             "content": r["content"], "created_at": r["created_at"].isoformat()}
            for r in rows
        ]})
    finally:
        conn.close()


@memory_bp.route("/api/memory/<int:memory_id>", methods=["DELETE"])
def delete_memory(memory_id):
    if "user_email" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    conn = db_connection()
    if not conn:
        return jsonify({"error": "DB error"}), 500
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_memories WHERE id = %s AND user_email = %s",
                (memory_id, session["user_email"])
            )
            deleted = cur.rowcount
        conn.commit()
        return jsonify({"ok": deleted > 0})
    finally:
        conn.close()
