from datetime import timedelta
from flask import Flask
from authlib.integrations.flask_client import OAuth
from config import _load_env
import os

_load_env()

app = Flask(__name__)

# Fail loudly rather than falling back to a publicly-known key — a guessable
# secret means anyone can forge a session cookie.
_secret_key = os.getenv("SECRET_KEY")
if not _secret_key:
    raise RuntimeError(
        "SECRET_KEY is not set. Add it to .env or the environment before starting ViperAI."
    )

app.secret_key = _secret_key
app.permanent_session_lifetime = timedelta(days=30)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
)

# ── Google OAuth ──────────────────────────────────────────────────────────────
oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)
app.extensions['oauth'] = oauth

# ── Blueprints ────────────────────────────────────────────────────────────────
from routes.routes import route_bp
from routes.auth   import auth_bp
from routes.chat   import chat_bp
from routes.admin  import admin_bp

app.register_blueprint(route_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(admin_bp)

if __name__ == '__main__':
    # The Werkzeug debugger is remote code execution — opt in explicitly,
    # never by default.
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
