import os
from datetime import timedelta
from config import _load_env
_load_env()

from flask import Flask, Response
from authlib.integrations.flask_client import OAuth

from routes.routes import route_bp
from routes.admin import admin_dp
from routes.chat import chat_bp
from routes.auth import auth_bp
from routes.memory import memory_bp

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', 'change-me-in-production')

is_production = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('RENDER') or os.environ.get('RAILWAY_ENVIRONMENT')
app.config.update(
    SESSION_COOKIE_SECURE=bool(is_production),
    SESSION_COOKIE_SAMESITE='None' if is_production else 'Lax',
    SESSION_COOKIE_HTTPONLY=True,
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)

oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

# make oauth accessible in auth blueprint
app.extensions['oauth'] = oauth

@app.route('/static/manifest.json')
def manifest():
    path = os.path.join(app.static_folder, 'manifest.json')
    with open(path) as f:
        data = f.read()
    return Response(data, mimetype='application/manifest+json')

@app.route('/static/service-worker.js')
def service_worker():
    path = os.path.join(app.static_folder, 'service-worker.js')
    with open(path) as f:
        data = f.read()
    resp = Response(data, mimetype='application/javascript')
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

app.register_blueprint(route_bp)
app.register_blueprint(admin_dp)
app.register_blueprint(chat_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(memory_bp)

if __name__ == "__main__":
    app.run(debug=True)