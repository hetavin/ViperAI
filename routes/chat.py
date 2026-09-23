import os

from flask import Blueprint, jsonify, request, session

from connect import db_connection
from services.llm_service import chat as llm_chat, LLMUnavailable
from services.memory_worker import start_memory_worker
from services.message_format import decode_message, encode_message


chat_bp = Blueprint(
    "chat_bp",
    __name__
)


# Attachment types whose contents can be handed to the model as text.
_TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".sql",
    ".yml", ".yaml", ".xml", ".ini", ".cfg", ".sh", ".java", ".c",
    ".cpp", ".h", ".go", ".rb", ".php", ".rs"
}

_MAX_INLINE_CHARS = 4000
_MAX_INLINE_FILES = 5


# ==================================================
# AUTH CHECK
# ==================================================

def _require_login():

    # Every handler below reads session["user_email"], so a cookie that carries
    # only user_id (an older session) must not be treated as logged in.
    if "user_id" not in session or not session.get("user_email"):

        return jsonify({
            "error": "Unauthorized"
        }), 401

    return None


def _read_attachments(uploads):
    """
    Turn uploaded files into (names, prompt_section).

    Text-like files are inlined up to a cap; anything else is named so the
    model can say it cannot read it, rather than the upload being silently
    discarded.
    """

    names = []
    sections = []

    for storage in uploads[:_MAX_INLINE_FILES]:

        name = os.path.basename(
            (storage.filename or "").strip()
        )

        if not name:
            continue

        names.append(name)

        suffix = os.path.splitext(name)[1].lower()

        if suffix not in _TEXT_SUFFIXES:
            sections.append(
                f"--- {name} (not a text file, contents unavailable) ---"
            )
            continue

        try:
            raw = storage.read(_MAX_INLINE_CHARS * 4)
            body = raw.decode("utf-8", "replace")

        except Exception as e:
            print(f"[Chat API] Could not read attachment {name}: {e}")
            sections.append(f"--- {name} (could not be read) ---")
            continue

        if len(body) > _MAX_INLINE_CHARS:
            body = body[:_MAX_INLINE_CHARS] + "\n...[truncated]"

        sections.append(f"--- {name} ---\n{body}")

    if not names:
        return [], ""

    return names, "\n\nAttached files:\n\n" + "\n\n".join(sections)


# ==================================================
# GET ALL CHATS
# GET /api/chats
# ==================================================

@chat_bp.route(
    "/api/chats",
    methods=["GET"]
)
def get_chats():

    err = _require_login()

    if err:
        return err


    conn = db_connection()

    if not conn:

        return jsonify({
            "error": "DB error"
        }), 500


    try:

        with conn.cursor() as cur:

            # --------------------------------------
            # Fetch user's chats
            # --------------------------------------

            cur.execute(
                """
                SELECT
                    id,
                    title,
                    created_at

                FROM chats

                WHERE user_email = %s

                ORDER BY updated_at DESC
                """,
                (
                    session["user_email"],
                )
            )

            rows = cur.fetchall()

            chat_ids = [row["id"] for row in rows]


            # --------------------------------------
            # Fetch every chat's messages in ONE
            # round trip, then group them by chat.
            #
            # Querying inside the loop above meant a
            # query per chat on every page load.
            # --------------------------------------

            by_chat = {chat_id: [] for chat_id in chat_ids}

            if chat_ids:

                placeholders = ", ".join(["%s"] * len(chat_ids))

                cur.execute(
                    f"""
                    SELECT
                        chat_id,
                        role,
                        message,
                        created_at

                    FROM chat_messages

                    WHERE chat_id IN ({placeholders})

                    ORDER BY id ASC
                    """,
                    tuple(chat_ids)
                )

                for m in cur.fetchall():

                    text, files = decode_message(m["message"])

                    by_chat[m["chat_id"]].append({

                        "role": m["role"],

                        "text": text,

                        "files": files,

                        "time": (
                            m["created_at"]
                            .isoformat()
                        )
                    })


            chats = [

                {
                    "id":
                        row["id"],

                    "title":
                        row["title"] or "New Chat",

                    "createdAt":
                        row["created_at"]
                        .isoformat(),

                    "messages":
                        by_chat.get(row["id"], [])
                }

                for row in rows
            ]


        return jsonify({
            "chats": chats
        }), 200


    except Exception as e:

        print(
            f"[Get Chats Error] {e}"
        )

        return jsonify({
            "error": "Failed to fetch chats"
        }), 500


    finally:

        conn.close()


# ==================================================
# DELETE ONE CHAT
# DELETE /api/chats/<id>
# ==================================================

@chat_bp.route(
    "/api/chats/<int:chat_id>",
    methods=["DELETE"]
)
def delete_chat(chat_id):

    err = _require_login()

    if err:
        return err


    conn = db_connection()

    if not conn:

        return jsonify({
            "error": "DB error"
        }), 500


    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                DELETE FROM chats

                WHERE id = %s
                AND user_email = %s
                """,
                (
                    chat_id,
                    session["user_email"]
                )
            )

            deleted = cur.rowcount


        conn.commit()


        if not deleted:

            return jsonify({
                "error": "Chat not found"
            }), 404


        return jsonify({
            "ok": True
        }), 200


    except Exception as e:

        conn.rollback()

        print(
            f"[Delete Chat Error] {e}"
        )

        return jsonify({
            "error": "Failed to delete chat"
        }), 500


    finally:

        conn.close()


# ==================================================
# RENAME ONE CHAT
# PATCH /api/chats/<id>
#
# The sidebar has always offered "Rename", but there
# was no endpoint behind it: the new title lived in
# the browser only and was lost on the next reload.
# ==================================================

@chat_bp.route(
    "/api/chats/<int:chat_id>",
    methods=["PATCH"]
)
def rename_chat(chat_id):

    err = _require_login()

    if err:
        return err


    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()

    if not title:

        return jsonify({
            "error": "Title is required"
        }), 400


    # title is VARCHAR(500) in the schema.
    title = title[:500]


    conn = db_connection()

    if not conn:

        return jsonify({
            "error": "DB error"
        }), 500


    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE chats

                SET title = %s

                WHERE id = %s
                AND user_email = %s
                """,
                (
                    title,
                    chat_id,
                    session["user_email"]
                )
            )

            updated = cur.rowcount


        conn.commit()


        if not updated:

            return jsonify({
                "error": "Chat not found"
            }), 404


        return jsonify({
            "ok": True,
            "title": title
        }), 200


    except Exception as e:

        conn.rollback()

        print(
            f"[Rename Chat Error] {e}"
        )

        return jsonify({
            "error": "Failed to rename chat"
        }), 500


    finally:

        conn.close()


# ==================================================
# DELETE ALL CHATS
# DELETE /api/chats
# ==================================================

@chat_bp.route(
    "/api/chats",
    methods=["DELETE"]
)
def delete_all_chats():

    err = _require_login()

    if err:
        return err


    conn = db_connection()

    if not conn:

        return jsonify({
            "error": "DB error"
        }), 500


    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                DELETE FROM chats

                WHERE user_email = %s
                """,
                (
                    session["user_email"],
                )
            )


        conn.commit()


        return jsonify({
            "ok": True
        }), 200


    except Exception as e:

        conn.rollback()

        print(
            f"[Delete All Chats Error] {e}"
        )

        return jsonify({
            "error": "Failed to delete chats"
        }), 500


    finally:

        conn.close()


# ==================================================
# MAIN CHAT API
# POST /chat
# ==================================================

@chat_bp.route(
    "/chat",
    methods=["POST"]
)
def chat():

    # ==================================================
    # 1. CHECK LOGIN
    # ==================================================

    err = _require_login()

    if err:
        return err


    user_email = session["user_email"]


    # ==================================================
    # 2. GET REQUEST DATA
    # ==================================================

    if (
        request.content_type
        and request.content_type.startswith(
            "multipart/form-data"
        )
    ):

        message = (
            request.form.get("message")
            or ""
        ).strip()

        chat_id = (
            request.form.get("chat_id")
            or None
        )

        title = (
            request.form.get("title")
            or message[:80]
        )

        uploads = request.files.getlist("files")

    else:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        message = (
            data.get("message")
            or ""
        ).strip()

        chat_id = (
            data.get("chat_id")
            or None
        )

        title = (
            data.get("title")
            or message[:80]
        )

        uploads = []


    # ==================================================
    # 3. VALIDATE MESSAGE
    # ==================================================

    if not message:

        return jsonify({
            "error": "Message is required"
        }), 400


    # ==================================================
    # 3b. READ ATTACHMENTS
    #
    # The client posts these as multipart "files"; they
    # used to be dropped on the floor.
    # ==================================================

    # The multipart branch yields a string; normalise so the response type
    # matches the JSON branch and a junk value is treated as "new chat".
    try:
        chat_id = int(chat_id) if chat_id else None
    except (TypeError, ValueError):
        chat_id = None

    # title is VARCHAR(500); an over-long one from a crafted request used to
    # fail the INSERT and surface as a generic 500.
    title = (title or '')[:500]

    attachment_names, attachment_text = _read_attachments(uploads)

    llm_message = message + attachment_text
    stored_message = encode_message(message, attachment_names)


    # ==================================================
    # 4. CONNECT DATABASE
    # ==================================================

    conn = db_connection()

    if not conn:

        return jsonify({
            "error": "DB error"
        }), 500


    try:

        with conn.cursor() as cur:


            # ==================================================
            # 5. VERIFY EXISTING CHAT
            # ==================================================

            if chat_id:

                cur.execute(
                    """
                    SELECT id

                    FROM chats

                    WHERE id = %s
                    AND user_email = %s
                    """,
                    (
                        chat_id,
                        user_email
                    )
                )


                # Chat doesn't belong to user
                # Create a new chat instead

                if not cur.fetchone():

                    chat_id = None


            # ==================================================
            # 6. CREATE NEW CHAT
            # ==================================================

            if not chat_id:

                cur.execute(
                    """
                    INSERT INTO chats
                    (
                        user_email,
                        user_name,
                        title
                    )

                    VALUES (%s, %s, %s)
                    """,
                    (
                        user_email,

                        session.get(
                            "user_name",
                            ""
                        ),

                        title
                    )
                )


                chat_id = (
                    cur.lastrowid
                )


            # ==================================================
            # 7. UPDATE EXISTING CHAT
            # ==================================================

            else:

                cur.execute(
                    """
                    UPDATE chats

                    SET
                        updated_at =
                        CURRENT_TIMESTAMP

                    WHERE id = %s
                    """,
                    (
                        chat_id,
                    )
                )


            # ==================================================
            # 8. FETCH PREVIOUS 6 MESSAGES
            #
            # IMPORTANT:
            # Fetch history BEFORE inserting current message.
            #
            # This prevents current query appearing twice:
            #
            # Current Query: What is Python?
            #
            # History:
            # USER: What is Python?
            # ==================================================

            cur.execute(
                """
                SELECT
                    role,
                    message

                FROM chat_messages

                WHERE chat_id = %s

                ORDER BY id DESC

                LIMIT 6
                """,
                (
                    chat_id,
                )
            )


            # SQL returns:
            # newest -> oldest
            #
            # LLM needs:
            # oldest -> newest

            history = [

                {
                    "role": r["role"],

                    # Older turns may be stored in the attachment JSON
                    # envelope — hand the model the text, not the envelope.
                    "message": decode_message(r["message"])[0]
                }

                for r in reversed(cur.fetchall())
            ]


            # ==================================================
            # 9. SAVE CURRENT USER MESSAGE
            # ==================================================

            cur.execute(
                """
                INSERT INTO chat_messages
                (
                    chat_id,
                    role,
                    message
                )

                VALUES
                (
                    %s,
                    'user',
                    %s
                )
                """,
                (
                    chat_id,
                    stored_message
                )
            )


        # Commit user message before LLM call

        conn.commit()


        # ==================================================
        # 10. CALL LLM SERVICE
        #
        # Argument 1 = Current user query
        # Argument 2 = User email for long-term memory
        # Argument 3 = Last 6 messages for short-term memory
        # ==================================================

        answer = llm_chat(
            llm_message,
            user_email,
            history
        )


        # ==================================================
        # 11. SAVE AI RESPONSE
        # ==================================================

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO chat_messages
                (
                    chat_id,
                    role,
                    message
                )

                VALUES
                (
                    %s,
                    'bot',
                    %s
                )
                """,
                (
                    chat_id,
                    answer
                )
            )


            # Update chat activity timestamp

            cur.execute(
                """
                UPDATE chats

                SET
                    updated_at =
                    CURRENT_TIMESTAMP

                WHERE id = %s
                """,
                (
                    chat_id,
                )
            )


        conn.commit()


        # ==================================================
        # 12. TRIGGER MEMORY PIPELINE (background)
        # ==================================================

        start_memory_worker(user_email, chat_id)


        # ==================================================
        # 13. RETURN ANSWER
        # ==================================================

        return jsonify({

            "answer":
                answer,

            "chat_id":
                chat_id

        }), 200


    except LLMUnavailable as e:

        # ==================================================
        # THE MODEL IS UNREACHABLE
        #
        # Say what is actually wrong — a bad key used to
        # surface as a blank "Something went wrong".
        # ==================================================

        try:
            conn.rollback()

        except Exception:
            pass


        print(
            f"[Chat API] LLM unavailable: {e}"
        )


        return jsonify({
            "error": str(e)
        }), 503


    except Exception as e:

        # ==================================================
        # ERROR HANDLING
        # ==================================================

        try:
            conn.rollback()

        except Exception:
            pass


        print(
            f"[Chat API Error] {e}"
        )


        return jsonify({
            "error": "Something went wrong"
        }), 500


    finally:

        conn.close()