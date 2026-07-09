from flask import Blueprint, request, jsonify, session
from threading import Thread
from services.llm_service import ask_llm
from connect import db_connection

chat_bp = Blueprint("chat", __name__)



def _save_to_db(user_email, user_name, chat_id, title, question, answer, result_box):
    conn = db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            if not chat_id:
                cur.execute(
                    "INSERT INTO chats (user_email, user_name, title) VALUES (%s, %s, %s)",
                    (user_email, user_name, title)
                )
                chat_id = cur.lastrowid
                result_box.append(chat_id)
            cur.execute(
                "INSERT INTO chat_messages (chat_id, role, message) VALUES (%s, 'user', %s)",
                (chat_id, question)
            )
            cur.execute(
                "INSERT INTO chat_messages (chat_id, role, message) VALUES (%s, 'bot', %s)",
                (chat_id, answer)
            )
        conn.commit()
    except Exception as e:
        print(f"DB save error: {e}")
    finally:
        conn.close()


@chat_bp.route("/chat", methods=["POST"])
def chat():
    data     = request.get_json()
    question = (data.get("message") or "").strip()
    chat_id  = data.get("chat_id")
    title    = data.get("title") or question[:60]

    if not question:
        return jsonify({"error": "Empty message"}), 400

    session_email = session.get("user_email")
    body_email    = (data.get("user_email") or "").strip().lower()
    body_name     = (data.get("user_name") or "").strip()
    user_email    = session_email or body_email
    user_name     = session.get("user_name") or body_name

    answer = ask_llm(question)

    result_box = []
    _save_to_db(
        user_email,
        user_name,
        chat_id,
        title,
        question,
        answer,
        result_box
    )

    if not chat_id and result_box:
        chat_id = result_box[0]

    return jsonify({"answer": answer, "chat_id": chat_id})


@chat_bp.route("/api/chats")
def get_user_chats():
    user_email = session.get("user_email") or request.args.get("email", "").strip().lower()
    if not user_email:
        return jsonify({"chats": []})

    conn = db_connection()
    if not conn:
        return jsonify({"chats": []})

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, created_at FROM chats WHERE user_email = %s ORDER BY created_at DESC",
                (user_email,)
            )
            chats = cur.fetchall()

            result = []
            for c in chats:
                cur.execute(
                    "SELECT role, message, created_at FROM chat_messages WHERE chat_id = %s ORDER BY created_at ASC",
                    (c["id"],)
                )
                messages = cur.fetchall()
                result.append({
                    "id": c["id"],
                    "title": c["title"],
                    "createdAt": c["created_at"].isoformat() + '+00:00',
                    "messages": [
                        {"role": m["role"], "text": m["message"], "time": m["created_at"].isoformat() + '+00:00'}
                        for m in messages
                    ]
                })
        return jsonify({"chats": result})
    except Exception as e:
        return jsonify({"chats": [], "error": str(e)})
    finally:
        conn.close()
