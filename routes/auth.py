from flask import Blueprint, jsonify, request, session, redirect, url_for, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from connect import db_connection

auth_bp = Blueprint('auth', __name__)

# Placeholder stored for accounts that can only sign in through Google.
GOOGLE_ONLY = "__google__"


def _ensure_users_table(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role ENUM('admin', 'user') NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
    conn.commit()


def _first_name(name, fallback="there"):
    """
    Greeting name. `name` is nullable in the schema and may be blank, so never
    index into the split() result directly.
    """
    parts = (name or "").split()
    return parts[0].capitalize() if parts else fallback


def _upgrade_password(conn, user_id, password):
    """Replace a legacy plaintext password with a hash, in place."""
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET password = %s WHERE id = %s",
                (generate_password_hash(password), user_id)
            )
        conn.commit()
    except Exception as e:
        print(f"[Auth] Password upgrade failed for user {user_id}: {e}")


def _verify_password(conn, user, password):
    stored = user.get("password") or ""

    if stored == GOOGLE_ONLY:
        return False

    try:
        if check_password_hash(stored, password):
            return True
    except Exception:
        pass

    # Rows created before hashing was introduced hold the password verbatim.
    # Accept them once, then upgrade so the plaintext does not survive a login.
    if stored and stored == password:
        _upgrade_password(conn, user["id"], password)
        return True

    return False


@auth_bp.route("/api/auth/me")
def me():
    if "user_id" not in session:
        return jsonify({"logged_in": False}), 200
    return jsonify({
        "logged_in": True,
        "name": session.get("user_name", "User"),
        "email": session.get("user_email", ""),
        "role": session.get("user_role", "user")
    }), 200


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"redirect": "/login"}), 200


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name     = (data.get("name") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm  = data.get("confirm_password") or ""
    agree    = data.get("agree", False)

    if not name or len(name) < 2:
        return jsonify({"error": "Name must be at least 2 characters"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "Enter a valid email address"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if password != confirm:
        return jsonify({"error": "Passwords do not match"}), 400
    if not agree:
        return jsonify({"error": "You must agree to the Terms of Service"}), 400

    conn = db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        _ensure_users_table(conn)
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                return jsonify({"error": "An account with this email already exists"}), 409
            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                (name, email, generate_password_hash(password))
            )
        conn.commit()
        return jsonify({
            "message": f"Welcome, {_first_name(name)}! Account created successfully."
        }), 201
    except Exception as e:
        conn.rollback()
        print(f"[Auth] Register error: {e}")
        return jsonify({"error": "Registration failed"}), 500
    finally:
        conn.close()


@auth_bp.route("/api/auth/login", methods=["POST"])
def login_api():
    data = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    conn = db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, password, role FROM users WHERE email = %s",
                (email,)
            )
            user = cursor.fetchone()

        if not user:
            return jsonify({
                "error": "No account found. Please register first.",
                "show_register": True
            }), 404

        if not _verify_password(conn, user, password):
            return jsonify({"error": "Incorrect password"}), 401

        session.permanent     = True
        session["user_id"]    = user["id"]
        session["user_name"]  = user["name"] or email
        session["user_email"] = email
        session["user_role"]  = user["role"]

        greeting = _first_name(user["name"])
        redirect_url = "/admin/dashboard" if user["role"] == "admin" else "/"
        return jsonify({
            "message": f"Welcome back, {greeting}!",
            "redirect": redirect_url
        }), 200
    except Exception as e:
        print(f"[Auth] Login error: {e}")
        return jsonify({"error": "Login failed"}), 500
    finally:
        conn.close()


@auth_bp.route("/api/auth/google")
def google_login():
    oauth = current_app.extensions['oauth']
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/api/auth/google/callback")
def google_callback():
    oauth = current_app.extensions['oauth']

    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        print(f"[Auth] Google token exchange failed: {e}")
        return redirect('/login?error=google_failed')

    user_info = token.get('userinfo') or {}
    email = (user_info.get('email') or "").strip().lower()
    if not email:
        return redirect('/login?error=google_failed')

    name = user_info.get('name') or email.split('@')[0]

    conn = db_connection()
    if not conn:
        return redirect('/login?error=db_failed')

    try:
        _ensure_users_table(conn)
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name, role FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if not user:
                cursor.execute(
                    "INSERT IGNORE INTO users (name, email, password) VALUES (%s, %s, %s)",
                    (name, email, GOOGLE_ONLY)
                )
                conn.commit()
                # Re-read rather than trusting lastrowid: a concurrent callback
                # for the same address may have won the INSERT.
                cursor.execute("SELECT id, name, role FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()

        if not user:
            print(f"[Auth] Google sign-in could not resolve a user row for {email}")
            return redirect('/login?error=google_failed')

        session.permanent     = True
        session["user_id"]    = user["id"]
        session["user_name"]  = user["name"] or name
        session["user_email"] = email
        session["user_role"]  = user["role"]
        return redirect("/admin/dashboard" if user["role"] == "admin" else "/")
    except Exception as e:
        conn.rollback()
        print(f"[Auth] Google callback error: {e}")
        return redirect('/login?error=google_failed')
    finally:
        conn.close()
