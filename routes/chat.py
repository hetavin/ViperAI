from flask import Blueprint, jsonify, request, session

from connect import db_connection
from services.llm_service import chat as llm_chat
from services.memory_worker import start_memory_worker


chat_bp = Blueprint(
    "chat_bp",
    __name__
)


# ==================================================
# AUTH CHECK
# ==================================================

def _require_login():

    if "user_id" not in session:

        return jsonify({
            "error": "Unauthorized"
        }), 401

    return None


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

            chats = []


            # --------------------------------------
            # Fetch messages for every chat
            # --------------------------------------

            for row in rows:

                cur.execute(
                    """
                    SELECT
                        role,
                        message,
                        created_at

                    FROM chat_messages

                    WHERE chat_id = %s

                    ORDER BY id ASC
                    """,
                    (
                        row["id"],
                    )
                )


                messages = [

                    {
                        "role": m["role"],

                        "text": m["message"],

                        "time": (
                            m["created_at"]
                            .isoformat()
                        )
                    }

                    for m in cur.fetchall()
                ]


                chats.append({

                    "id":
                        row["id"],

                    "title":
                        row["title"],

                    "createdAt":
                        row["created_at"]
                        .isoformat(),

                    "messages":
                        messages
                })


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


        conn.commit()


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


    # ==================================================
    # 3. VALIDATE MESSAGE
    # ==================================================

    if not message:

        return jsonify({
            "error": "Message is required"
        }), 400


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

            history = list(
                reversed(
                    cur.fetchall()
                )
            )


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
                    message
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
            message,
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