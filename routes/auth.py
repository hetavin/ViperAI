from flask import Blueprint, jsonify, render_template, request, session, redirect, url_for, current_app
from connect import db_connection

auth_bp = Blueprint('auth', __name__)


def _ensure_users_table(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role ENUM('admin', 'user') NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()


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
    return jsonify({"redirect": "/"}), 200


@auth_bp.route("/login")
def login_page():
    return render_template("auth.html")


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
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
                (name, email, password)
            )
        conn.commit()
        first = name.split()[0].capitalize()
        return jsonify({"message": f"Welcome, {first}! Account created successfully."}), 201
    finally:
        conn.close()


@auth_bp.route("/api/auth/login", methods=["POST"])
def login_api():
    data = request.get_json()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    conn = db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name, password, role FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

        if not user:
            return jsonify({"error": "No account found. Please register first.", "show_register": True}), 404

        if not password:
            return jsonify({"error": "Incorrect password"}), 401

        session.permanent    = True
        session["user_id"]    = user["id"]
        session["user_name"]  = user["name"]
        session["user_email"] = email
        session["user_role"]  = user["role"]
        first = user["name"].split()[0].capitalize()
        redirect_url = "/admin/dashboard" if user["role"] == "admin" else "/"
        return jsonify({"message": f"Welcome back, {first}!", "redirect": redirect_url}), 200
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
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')
    if not user_info:
        return redirect('/login?error=google_failed')

    email = user_info['email'].lower()
    name  = user_info.get('name', email.split('@')[0])

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
                    "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                    (name, email, '__google__')
                )
                conn.commit()
                cursor.execute("SELECT id, name, role FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()

        session.permanent    = True
        session["user_id"]    = user["id"]
        session["user_name"]  = user["name"]
        session["user_email"] = email
        session["user_role"]  = user["role"]
        return redirect("/admin/dashboard" if user["role"] == "admin" else "/")
    finally:
        conn.close()
