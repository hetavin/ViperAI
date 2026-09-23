import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from flask import Blueprint, jsonify, request, session, redirect, url_for, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from connect import db_connection

auth_bp = Blueprint('auth', __name__)

# Placeholder stored for accounts that can only sign in through Google.
GOOGLE_ONLY = "__google__"

# Password reset codes.
OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_SECONDS = 30


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


# ==============================================================================
# PASSWORD RESET
#
# The login screen has always shown a three-step "Forgot password?" flow, but
# nothing was behind it: the forms called doSendOtp / doVerifyOtp /
# doResetPassword, none of which existed, so submitting the first step threw a
# ReferenceError and reloaded the page. These are the endpoints those steps
# now talk to.
#
# Delivery needs SMTP credentials in the environment (SMTP_HOST, SMTP_USER,
# SMTP_PASSWORD, optionally SMTP_PORT / SMTP_FROM / SMTP_STARTTLS). Without
# them the flow says resets are unavailable rather than pretending a code was
# sent.
# ==============================================================================

def _ensure_reset_table(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_resets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                code_hash VARCHAR(255) NOT NULL,
                expires_at DATETIME NOT NULL,
                attempts INT NOT NULL DEFAULT 0,
                used TINYINT(1) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_email (email)
            )
        """)
    conn.commit()


def _smtp_settings():
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")

    if not host or not user or not password:
        return None

    return {
        "host": host,
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": user,
        "password": password,
        "sender": os.getenv("SMTP_FROM", "").strip() or user,
        "starttls": os.getenv("SMTP_STARTTLS", "1") == "1",
    }


def _send_otp_email(to_email, code):
    """Hand the code to the configured SMTP server."""

    smtp = _smtp_settings()

    if not smtp:
        return False

    message = EmailMessage()
    message["Subject"] = "Your ViperAI password reset code"
    message["From"] = smtp["sender"]
    message["To"] = to_email
    message.set_content(
        "Your ViperAI verification code is {code}.\n\n"
        "It expires in {minutes} minutes. If you did not ask to reset your "
        "password, you can ignore this email.".format(
            code=code, minutes=OTP_TTL_MINUTES
        )
    )

    if smtp["port"] == 465:
        with smtplib.SMTP_SSL(smtp["host"], smtp["port"], timeout=10) as server:
            server.login(smtp["user"], smtp["password"])
            server.send_message(message)
        return True

    with smtplib.SMTP(smtp["host"], smtp["port"], timeout=10) as server:
        if smtp["starttls"]:
            server.starttls()
        server.login(smtp["user"], smtp["password"])
        server.send_message(message)

    return True


@auth_bp.route("/api/auth/forgot/send", methods=["POST"])
def forgot_send():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "Enter a valid email address"}), 400

    if not _smtp_settings():
        return jsonify({
            "error": "Password reset email is not configured on this server."
        }), 503

    conn = db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        _ensure_users_table(conn)
        _ensure_reset_table(conn)

        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if not cursor.fetchone():
                return jsonify({"error": "No account found with that email"}), 404

            # Throttle server-side too: the 30s button timer is only a hint.
            cursor.execute(
                """
                SELECT created_at FROM password_resets
                WHERE email = %s ORDER BY id DESC LIMIT 1
                """,
                (email,)
            )
            last = cursor.fetchone()

        if last and last["created_at"]:
            age = (datetime.now() - last["created_at"]).total_seconds()
            if age < OTP_RESEND_SECONDS:
                wait = int(OTP_RESEND_SECONDS - age) + 1
                return jsonify({
                    "error": "Please wait {}s before requesting another code".format(wait)
                }), 429

        code = "{:06d}".format(secrets.randbelow(1000000))

        with conn.cursor() as cursor:
            # Any earlier code for this address is void from here on.
            cursor.execute("DELETE FROM password_resets WHERE email = %s", (email,))
            cursor.execute(
                """
                INSERT INTO password_resets (email, code_hash, expires_at)
                VALUES (%s, %s, %s)
                """,
                (
                    email,
                    generate_password_hash(code),
                    datetime.now() + timedelta(minutes=OTP_TTL_MINUTES)
                )
            )
        conn.commit()

        try:
            _send_otp_email(email, code)
        except Exception as e:
            print("[Auth] Reset email to {} failed: {}".format(email, e))
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM password_resets WHERE email = %s", (email,))
            conn.commit()
            return jsonify({"error": "Could not send the email. Try again later."}), 502

        session["pw_reset_email"] = email
        session.pop("pw_reset_verified", None)

        return jsonify({
            "message": "Verification code sent to {}".format(email),
            "expires_in": OTP_TTL_MINUTES * 60
        }), 200

    except Exception as e:
        conn.rollback()
        print("[Auth] Forgot-send error: {}".format(e))
        return jsonify({"error": "Could not start the password reset"}), 500
    finally:
        conn.close()


@auth_bp.route("/api/auth/forgot/verify", methods=["POST"])
def forgot_verify():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or session.get("pw_reset_email") or "").strip().lower()
    code = (data.get("code") or "").strip()

    if not email or not code:
        return jsonify({"error": "Enter the 6-digit code"}), 400

    conn = db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        _ensure_reset_table(conn)

        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, code_hash, expires_at, attempts, used
                FROM password_resets
                WHERE email = %s ORDER BY id DESC LIMIT 1
                """,
                (email,)
            )
            row = cursor.fetchone()

        if not row or row["used"]:
            return jsonify({"error": "Request a new code"}), 400

        if row["expires_at"] < datetime.now():
            return jsonify({"error": "That code has expired. Request a new one."}), 400

        if row["attempts"] >= OTP_MAX_ATTEMPTS:
            return jsonify({"error": "Too many attempts. Request a new code."}), 429

        if not check_password_hash(row["code_hash"], code):
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE password_resets SET attempts = attempts + 1 WHERE id = %s",
                    (row["id"],)
                )
            conn.commit()

            left = OTP_MAX_ATTEMPTS - row["attempts"] - 1
            detail = ""
            if left > 0:
                detail = " - {} attempt{} left".format(left, "" if left == 1 else "s")

            return jsonify({"error": "Incorrect code" + detail}), 400

        session["pw_reset_email"] = email
        session["pw_reset_verified"] = row["id"]

        return jsonify({"message": "Code verified"}), 200

    except Exception as e:
        conn.rollback()
        print("[Auth] Forgot-verify error: {}".format(e))
        return jsonify({"error": "Could not verify the code"}), 500
    finally:
        conn.close()


@auth_bp.route("/api/auth/forgot/reset", methods=["POST"])
def forgot_reset():
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or ""

    email = session.get("pw_reset_email")
    reset_id = session.get("pw_reset_verified")

    if not email or not reset_id:
        return jsonify({"error": "Verify your code again"}), 403

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if password != confirm:
        return jsonify({"error": "Passwords do not match"}), 400

    conn = db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor() as cursor:
            # The code may have expired or been spent between verify and here.
            cursor.execute(
                """
                SELECT expires_at, used FROM password_resets
                WHERE id = %s AND email = %s
                """,
                (reset_id, email)
            )
            row = cursor.fetchone()

        if not row or row["used"] or row["expires_at"] < datetime.now():
            session.pop("pw_reset_verified", None)
            return jsonify({"error": "That code has expired. Start again."}), 400

        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET password = %s WHERE email = %s",
                (generate_password_hash(password), email)
            )
            updated = cursor.rowcount
            cursor.execute(
                "UPDATE password_resets SET used = 1 WHERE id = %s",
                (reset_id,)
            )
        conn.commit()

        if not updated:
            return jsonify({"error": "No account found with that email"}), 404

        session.pop("pw_reset_email", None)
        session.pop("pw_reset_verified", None)

        return jsonify({"message": "Password changed successfully"}), 200

    except Exception as e:
        conn.rollback()
        print("[Auth] Forgot-reset error: {}".format(e))
        return jsonify({"error": "Could not change the password"}), 500
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
