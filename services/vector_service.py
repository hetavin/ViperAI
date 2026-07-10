import struct
from sentence_transformers import SentenceTransformer
from connect import db_connection

_model = SentenceTransformer("all-MiniLM-L6-v2")


def _to_blob(vector) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS message_embeddings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message_id INT NOT NULL UNIQUE,
                chat_id INT NOT NULL,
                role ENUM('user', 'bot') NOT NULL,
                embedding LONGBLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE,
                FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
                INDEX idx_chat_id (chat_id)
            )
        """)
    conn.commit()


def save_embedding(message_id: int, chat_id: int, role: str, text: str):
    vector = _model.encode(text).tolist()
    blob = _to_blob(vector)
    conn = db_connection()
    if not conn:
        return
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT IGNORE INTO message_embeddings (message_id, chat_id, role, embedding) VALUES (%s, %s, %s, %s)",
                (message_id, chat_id, role, blob)
            )
        conn.commit()
    finally:
        conn.close()


def save_memory_embedding(memory_id: int, content: str):
    """Encode memory content and update its embedding in user_memories."""
    blob = _to_blob(_model.encode(content).tolist())
    conn = db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE user_memories SET embedding = %s WHERE id = %s",
                (blob, memory_id)
            )
        conn.commit()
    finally:
        conn.close()


def sync_all_embeddings():
    """Bulk embed all chat_messages that don't yet have an embedding."""
    conn = db_connection()
    if not conn:
        return 0
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cm.id, cm.chat_id, cm.role, cm.message
                FROM chat_messages cm
                LEFT JOIN message_embeddings me ON me.message_id = cm.id
                WHERE me.id IS NULL
            """)
            rows = cur.fetchall()

        if not rows:
            return 0

        texts = [r["message"] for r in rows]
        vectors = _model.encode(texts, batch_size=64, show_progress_bar=False).tolist()

        with conn.cursor() as cur:
            cur.executemany(
                "INSERT IGNORE INTO message_embeddings (message_id, chat_id, role, embedding) VALUES (%s, %s, %s, %s)",
                [(r["id"], r["chat_id"], r["role"], _to_blob(v)) for r, v in zip(rows, vectors)]
            )
        conn.commit()
        return len(rows)
    finally:
        conn.close()
