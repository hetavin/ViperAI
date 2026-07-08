from flask import Flask

from routes.routes import route_bp
from routes.admin import admin_dp
from routes.chat import chat_bp
from routes.auth import auth_bp

app = Flask(__name__)

app.secret_key = 'your-secret-key-here'

app.register_blueprint(route_bp)
app.register_blueprint(admin_dp)
app.register_blueprint(chat_bp)
app.register_blueprint(auth_bp)

if __name__ == "__main__":
    app.run(debug=True)