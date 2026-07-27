from datetime import timedelta
from flask import Flask
from authlib.integrations.flask_client import OAuth
from config import _load_env
import os

_load_env()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "viper-secret-key")
app.permanent_session_lifetime = timedelta(days=30)

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
    app.run(debug=True)