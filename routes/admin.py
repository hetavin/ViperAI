from flask import render_template, Blueprint, jsonify
from connect import db_connection
from urllib.parse import unquote


admin_dp = Blueprint('admin', __name__)


@admin_dp.route('/admin/dashboard')
def admin_dashboard():
    return render_template('admin.html')


@admin_dp.route('/api/admin/stats')
def get_stats():
    conn = db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM users")
            users = cur.fetchone()['cnt']
            cur.execute("SELECT COUNT(*) AS cnt FROM chats")
            chats = cur.fetchone()['cnt']
            cur.execute("SELECT COUNT(*) AS cnt FROM chat_messages")
            messages = cur.fetchone()['cnt']
        return jsonify({'users': users, 'chats': chats, 'messages': messages})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@admin_dp.route('/api/admin/users')
def get_users():
    conn = db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.name, u.email, u.created_at,
                       COUNT(DISTINCT c.id) AS chat_count,
                       COUNT(m.id)          AS message_count
                FROM users u
                LEFT JOIN chats c ON c.user_email = u.email
                LEFT JOIN chat_messages m ON m.chat_id = c.id
                GROUP BY u.id
                ORDER BY u.created_at DESC
            """)
            users = cur.fetchall()
        return jsonify({'users': [
            {
                'id': u['id'], 'name': u['name'], 'email': u['email'],
                'created_at': str(u['created_at']),
                'chat_count': u['chat_count'], 'message_count': u['message_count']
            }
            for u in users
        ]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@admin_dp.route('/api/admin/users/<user_email>/chats')
def get_user_chats(user_email):
    conn = db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, created_at FROM chats WHERE user_email = %s ORDER BY created_at DESC",
                (unquote(user_email),)
            )
            chats = cur.fetchall()
        return jsonify({'chats': [
            {'id': c['id'], 'title': c['title'], 'created_at': str(c['created_at'])}
            for c in chats
        ]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@admin_dp.route('/api/admin/chats/<int:chat_id>/messages')
def get_chat_messages(chat_id):
    conn = db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, message, created_at FROM chat_messages WHERE chat_id = %s ORDER BY created_at ASC",
                (chat_id,)
            )
            messages = cur.fetchall()
        return jsonify({'messages': [
            {'role': m['role'], 'message': m['message'], 'created_at': str(m['created_at'])}
            for m in messages
        ]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
