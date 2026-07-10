from flask import Blueprint, request, jsonify, session
from threading import Thread
import base64
import json
from services.llm_service import ask_llm
from connect import db_connection

chat_bp = Blueprint("chat", __name__)


def _extract_file_contents(files):
    """Read uploaded files and return list of dicts for ask_llm."""
    result = []
    for f in files:
        mime = f.content_type or ""
        raw = f.read()
        if mime.startswith("image/"):
            result.append({
                "type": "image",
                "name": f.filename,
                "mime": mime,
                "data": base64.b64encode(raw).decode()
            })
        else:
            # Try to decode as text (txt, csv, md, code files)
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                text = raw.decode("latin-1", errors="replace")
            result.append({
                "type": "text",
                "name": f.filename,
                "data": text[:12000]  # cap at 12k chars to stay within token limits
            })
    return result



def _parse_msg(role, message, created_at):
    entry = {'role': role, 'time': created_at.isoformat() + '+00:00'}
    if role == 'user' and message.startswith('{'):
        try:
            p = json.loads(message)
            entry['text'] = p.get('text', message)
            entry['files'] = p.get('files', [])
            return entry
        except Exception:
            pass
    entry['text'] = message
    return entry


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
    # Support both JSON (no files) and multipart/form-data (with files)
    if request.content_type and "multipart/form-data" in request.content_type:
        question  = (request.form.get("message") or "").strip()
        chat_id   = request.form.get("chat_id") or None
        title     = request.form.get("title") or question[:60]
        body_email = (request.form.get("user_email") or "").strip().lower()
        body_name  = (request.form.get("user_name") or "").strip()
        files      = request.files.getlist("files")
        file_contents = _extract_file_contents(files) if files else []
        file_names = [f.filename for f in files] if files else []
    else:
        data       = request.get_json()
        question   = (data.get("message") or "").strip()
        chat_id    = data.get("chat_id")
        title      = data.get("title") or question[:60]
        body_email = (data.get("user_email") or "").strip().lower()
        body_name  = (data.get("user_name") or "").strip()
        file_contents = []
        file_names = []

    if not question:
        return jsonify({"error": "Empty message"}), 400

    session_email = session.get("user_email")
    user_email    = session_email or body_email
    user_name     = session.get("user_name") or body_name

    answer = ask_llm(question, file_contents if file_contents else None)

    stored_question = (json.dumps({'files': file_names, 'text': question}) if file_names else question)

    result_box = []
    _save_to_db(
        user_email,
        user_name,
        chat_id,
        title,
        stored_question,
        answer,
        result_box
    )

    if not chat_id and result_box:
        chat_id = result_box[0]

    return jsonify({"answer": answer, "chat_id": chat_id})


@chat_bp.route("/api/chats/<int:chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    user_email = session.get("user_email") or request.args.get("email", "").strip().lower()
    if not user_email:
        return jsonify({"error": "Unauthorized"}), 401
    conn = db_connection()
    if not conn:
        return jsonify({"error": "DB error"}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chats WHERE id = %s AND user_email = %s", (chat_id, user_email))
            deleted = cur.rowcount
        conn.commit()
        return jsonify({"ok": deleted > 0})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@chat_bp.route("/api/chats", methods=["DELETE"])
def delete_all_chats():
    user_email = session.get("user_email") or request.args.get("email", "").strip().lower()
    if not user_email:
        return jsonify({"error": "Unauthorized"}), 401
    conn = db_connection()
    if not conn:
        return jsonify({"error": "DB error"}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chats WHERE user_email = %s", (user_email,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


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
                        _parse_msg(m["role"], m["message"], m["created_at"])
                        for m in messages
                    ]
                })
        return jsonify({"chats": result})
    except Exception as e:
        return jsonify({"chats": [], "error": str(e)})
    finally:
        conn.close()
