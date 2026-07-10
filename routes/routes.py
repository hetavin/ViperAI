from flask import Flask, render_template, Blueprint, session, redirect
from functools import wraps
from connect import db_connection

route_bp = Blueprint('routes', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' in session:
            return f(*args, **kwargs)
        # fallback: verify email from session against DB (handles deploy session loss)
        email = session.get('user_email')
        if email:
            conn = db_connection()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT id, role FROM users WHERE email = %s", (email,))
                        row = cur.fetchone()
                    if row:
                        session['user_id']   = row['id']
                        session['user_role'] = row['role']
                        return f(*args, **kwargs)
                except Exception:
                    pass
                finally:
                    conn.close()
        return redirect('/login')
    return decorated


@route_bp.route('/')
@login_required
def index():
    return render_template('index.html')


@route_bp.route('/admin')
def admin():
    return redirect('/admin/dashboard')
