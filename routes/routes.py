from flask import Blueprint, current_app, redirect, render_template, send_from_directory, session

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


@route_bp.route('/service-worker.js')
def service_worker():
    """
    Serve the worker from the site root.

    Registering /static/service-worker.js with scope "/" is rejected by the
    browser (SecurityError) because a worker may only control its own
    directory and below, so registration failed outright and nothing was ever
    cached. Served from here the scope is legitimate; the header keeps it
    valid even if the file moves back under /static.
    """
    response = send_from_directory(
        current_app.static_folder, 'service-worker.js',
        mimetype='application/javascript'
    )
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache'
    return response
