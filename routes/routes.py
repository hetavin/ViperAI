from flask import Flask, Blueprint, render_template, redirect

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
    return render_template("admin.html")