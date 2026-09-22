from flask import Blueprint, render_template, redirect, session

route_bp = Blueprint('route_bp', __name__)

@route_bp.route('/')
def index():
    return render_template("index.html")

@route_bp.route('/login')
def login():
    return render_template("auth.html")

@route_bp.route('/register')
def register():
    return redirect('/login?mode=register')

@route_bp.route('/admin/dashboard')
def admin():
    # The admin APIs are gated separately, but the page itself must not render
    # for anyone who is not an admin.
    if session.get('user_role') != 'admin':
        return redirect('/login')
    return render_template("admin.html")
