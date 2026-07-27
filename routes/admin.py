from flask import Blueprint, jsonify, session
from connect import db_connection
from functools import wraps

admin_bp = Blueprint('admin_bp', __name__)


def _admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_role') != 'admin':
            return jsonify({'error': 'Forbidden'}), 403
        return f(*args, **kwargs)
    return decorated


# ── GET /api/admin/dashboard ──────────────────────────────────────────────────
@admin_bp.route('/api/admin/dashboard')
@_admin_required
def dashboard():
    conn = db_connection()
    if not conn:
        return jsonify({'error': 'DB error'}), 500
    try:
        with conn.cursor() as cur:

            cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE role = 'user'")
            total_users = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) AS cnt FROM chats")
            total_chats = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) AS cnt FROM chat_messages")
            total_messages = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) AS cnt FROM user_memories")
            total_memories = cur.fetchone()['cnt']

            # Recent 6 chats with message count
            cur.execute("""
                SELECT c.id, c.title, c.user_email, c.user_name,
                       c.updated_at, COUNT(m.id) AS msg_count
                FROM chats c
                LEFT JOIN chat_messages m ON m.chat_id = c.id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT 6
            """)
            recent_chats = [
                {
                    'id':         r['id'],
                    'title':      r['title'] or 'Untitled',
                    'user_email': r['user_email'],
                    'user_name':  r['user_name'] or r['user_email'],
                    'msg_count':  r['msg_count'],
                    'updated_at': r['updated_at'].isoformat(),
                }
                for r in cur.fetchall()
            ]

            # Top 6 users by message count
            cur.execute("""
                SELECT u.name, u.email, u.created_at,
                       COUNT(DISTINCT c.id)  AS chat_count,
                       COUNT(DISTINCT m.id)  AS message_count
                FROM users u
                LEFT JOIN chats c         ON c.user_email = u.email
                LEFT JOIN chat_messages m ON m.chat_id    = c.id
                WHERE u.role = 'user'
                GROUP BY u.id
                ORDER BY message_count DESC
                LIMIT 6
            """)
            top_users = [
                {
                    'name':          r['name'] or r['email'],
                    'email':         r['email'],
                    'created_at':    r['created_at'].isoformat(),
                    'chat_count':    r['chat_count'],
                    'message_count': r['message_count'],
                }
                for r in cur.fetchall()
            ]

        return jsonify({
            'stats': {
                'users':    total_users,
                'chats':    total_chats,
                'messages': total_messages,
                'memories': total_memories,
            },
            'recent_chats': recent_chats,
            'top_users':    top_users,
        }), 200
    finally:
        conn.close()


# ── GET /api/admin/stats ──────────────────────────────────────────────────────
@admin_bp.route('/api/admin/stats')
@_admin_required
def stats():
    conn = db_connection()
    if not conn:
        return jsonify({'error': 'DB error'}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE role = 'user'")
            users = cur.fetchone()['cnt']
            cur.execute("SELECT COUNT(*) AS cnt FROM chat_messages")
            messages = cur.fetchone()['cnt']
            cur.execute("SELECT COUNT(*) AS cnt FROM chats")
            chats = cur.fetchone()['cnt']
        return jsonify({'users': users, 'messages': messages, 'chats': chats}), 200
    finally:
        conn.close()


# ── GET /api/admin/users ──────────────────────────────────────────────────────
@admin_bp.route('/api/admin/users')
@_admin_required
def get_users():
    conn = db_connection()
    if not conn:
        return jsonify({'error': 'DB error'}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.name, u.email, u.role, u.created_at,
                       COUNT(DISTINCT c.id)  AS chat_count,
                       COUNT(DISTINCT m.id)  AS message_count
                FROM users u
                LEFT JOIN chats c         ON c.user_email = u.email
                LEFT JOIN chat_messages m ON m.chat_id    = c.id
                GROUP BY u.id
                ORDER BY u.created_at DESC
            """)
            rows = cur.fetchall()
        users = [
            {
                'id':            r['id'],
                'name':          r['name'] or '',
                'email':         r['email'],
                'role':          r['role'],
                'created_at':    r['created_at'].isoformat(),
                'chat_count':    r['chat_count'],
                'message_count': r['message_count'],
            }
            for r in rows
        ]
        return jsonify({'users': users}), 200
    finally:
        conn.close()


# ── GET /api/admin/users/<email>/chats ────────────────────────────────────────
@admin_bp.route('/api/admin/users/<path:email>/chats')
@_admin_required
def get_user_chats(email):
    conn = db_connection()
    if not conn:
        return jsonify({'error': 'DB error'}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, created_at, updated_at
                FROM chats WHERE user_email = %s
                ORDER BY updated_at DESC
            """, (email,))
            rows = cur.fetchall()
        chats = [
            {
                'id':         r['id'],
                'title':      r['title'] or 'Untitled',
                'created_at': r['created_at'].isoformat(),
                'updated_at': r['updated_at'].isoformat(),
            }
            for r in rows
        ]
        return jsonify({'chats': chats}), 200
    finally:
        conn.close()


# ── GET /api/admin/chats/<id>/messages ────────────────────────────────────────
@admin_bp.route('/api/admin/chats/<int:chat_id>/messages')
@_admin_required
def get_chat_messages(chat_id):
    conn = db_connection()
    if not conn:
        return jsonify({'error': 'DB error'}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT role, message, created_at
                FROM chat_messages WHERE chat_id = %s
                ORDER BY id ASC
            """, (chat_id,))
            rows = cur.fetchall()
        messages = [
            {
                'role':       r['role'],
                'message':    r['message'],
                'created_at': r['created_at'].isoformat(),
            }
            for r in rows
        ]
        return jsonify({'messages': messages}), 200
    finally:
        conn.close()


# ── GET /api/admin/me ─────────────────────────────────────────────────────────
@admin_bp.route('/api/admin/me')
@_admin_required
def admin_me():
    return jsonify({
        'name':  session.get('user_name', 'Admin'),
        'email': session.get('user_email', ''),
    }), 200
