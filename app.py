import os
from config import _load_env
_load_env()

from flask import Flask

from routes.routes import route_bp
from routes.admin import admin_dp
from routes.chat import chat_bp
from routes.auth import auth_bp

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', 'change-me-in-production')

is_production = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('RENDER') or os.environ.get('RAILWAY_ENVIRONMENT')
app.config.update(
    SESSION_COOKIE_SECURE=bool(is_production),
    SESSION_COOKIE_SAMESITE='None' if is_production else 'Lax',
    SESSION_COOKIE_HTTPONLY=True,
)

app.register_blueprint(route_bp)
app.register_blueprint(admin_dp)
app.register_blueprint(chat_bp)
app.register_blueprint(auth_bp)

if __name__ == "__main__":
    app.run(debug=True)