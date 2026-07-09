from flask import render_template, Blueprint, jsonify, session, redirect, url_for
from functools import wraps
from connect import db_connection
from urllib.parse import unquote

admin_dp = Blueprint('admin', __name__)


def _check_admin():
    """Returns True if current request is from an admin (session or DB lookup)."""
    if session.get('user_role') == 'admin':
        return True
    email = session.get('user_email')
    if not email:
        return False
    conn = db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
        if row and row['role'] == 'admin':
            session['user_role'] = 'admin'
            return True
        return False
    except Exception:
        return False
    finally:
        conn.close()


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _check_admin():
            return jsonify({'error': 'Forbidden'}), 403
        return f(*args, **kwargs)
    return decorated


@admin_dp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    if not _check_admin():
        return redirect('/')
    return render_template('admin.html')


@admin_dp.route('/api/admin/stats')
@admin_required
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
@admin_required
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
                'created_at': str(u['created_at']) + ' UTC',
                'chat_count': u['chat_count'], 'message_count': u['message_count']
            }
            for u in users
        ]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@admin_dp.route('/api/admin/users/<user_email>/chats')
@admin_required
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
            {'id': c['id'], 'title': c['title'], 'created_at': str(c['created_at']) + ' UTC'}
            for c in chats
        ]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@admin_dp.route('/api/admin/chats/<int:chat_id>/messages')
@admin_required
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
            {'role': m['role'], 'message': m['message'], 'created_at': str(m['created_at']) + ' UTC'}
            for m in messages
        ]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()
