from flask import Flask, render_template, Blueprint

route_bp = Blueprint('routes', __name__)

@route_bp.route('/')
def index():
    return render_template('index.html')


@route_bp.route('/admin')
def admin():
    return render_template('admin.html')

