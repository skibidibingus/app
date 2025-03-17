import os
import random
import string
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, redirect, url_for, flash, Response
from flask import render_template_string
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'CHANGE_THIS')

# Configure PostgreSQL database
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL is None:
    # Fallback to SQLite if DATABASE_URL is not set
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///eaglehub_complex.db'
else:
    # Use PostgreSQL
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

############################
# Database Models
############################

class User(db.Model):
    """Placeholder user model (not fully used here)."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Project(db.Model):
    """Projects in EagleHub (like script hubs)."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Script(db.Model):
    """Scripts belonging to a project."""
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    version = db.Column(db.String(20), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class BlockedIP(db.Model):
    """Example of blocked IP addresses with a reason."""
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), nullable=False)
    reason = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class KillSwitch(db.Model):
    """Toggle to disable all scripts if active is True."""
    id = db.Column(db.Integer, primary_key=True)
    active = db.Column(db.Boolean, default=False)

class Revenue(db.Model):
    """Monthly revenue or monthly execution data for a line chart."""
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(20), nullable=False)  # e.g. 'Jan','Feb'...
    amount = db.Column(db.Integer, nullable=False)    # e.g. 500, 1000, etc.

class Key(db.Model):
    """Keys for whitelisting logic (like Luarmor)."""
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(64), unique=True, nullable=False)
    hwid = db.Column(db.String(128), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

############################
# NEW: Loader Models
############################

class MainScript(db.Model):
    """
    Multi-chunk script storage for loader.
    chunk_index = 1,2,...
    code = raw Lua chunk
    """
    id = db.Column(db.Integer, primary_key=True)
    chunk_index = db.Column(db.Integer, default=1)
    code = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class EphemeralRoute(db.Model):
    """
    Short-lived route for each chunk with advanced checks.
    Using a new table name to avoid conflicts if you had an old ephemeral_route table.
    """
    __tablename__ = "ephemeral_routes_v2"
    id = db.Column(db.Integer, primary_key=True)
    route_name = db.Column(db.String(50), unique=True, nullable=False)
    token = db.Column(db.String(64), nullable=False)
    chunk_index = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_in = db.Column(db.Integer, default=120)
    single_use = db.Column(db.Boolean, default=True)

############################
# Seed Data
############################
def seed_data():
    """Seed the database with sample data if empty."""
    # Create a demo user
    if not User.query.first():
        u = User(username='demo')
        db.session.add(u)

    # Create a sample project
    if not Project.query.first():
        p = Project(name="EagleHub Master Project")
        db.session.add(p)
        db.session.commit()
        s1 = Script(project_id=p.id, name="Roofing Energy Visualizer", version="v1.0")
        s2 = Script(project_id=p.id, name="PetMaster", version="v1.2")
        s3 = Script(project_id=p.id, name="Jailbreak Auto [Premium]", version="v0.9.2")
        db.session.add_all([s1, s2, s3])

    # Some blocked IPs
    if not BlockedIP.query.first():
        b1 = BlockedIP(ip_address="192.168.0.15", reason="Suspicious activity")
        b2 = BlockedIP(ip_address="10.0.0.99", reason="Excessive requests")
        db.session.add_all([b1, b2])

    # Kill switch
    if not KillSwitch.query.first():
        ks = KillSwitch(active=False)
        db.session.add(ks)

    # Revenue chart data
    if not Revenue.query.first():
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug"]
        for m in months:
            r = Revenue(month=m, amount=random.randint(300, 2000))
            db.session.add(r)

    # Sample keys
    if not Key.query.first():
        from datetime import timedelta
        k1 = Key(value="ABCDEF1234567890", hwid=None, expires_at=None)
        k2 = Key(value="HELLO987654321", hwid="HWID-TEST", expires_at=datetime.utcnow()+timedelta(days=7))
        db.session.add_all([k1, k2])

    # If no main script chunks, add some
    if not MainScript.query.first():
        c1 = MainScript(chunk_index=1, code="print('Hello from chunk #1!')", updated_at=datetime.utcnow())
        c2 = MainScript(chunk_index=2, code="print('Hello from chunk #2! This is the final chunk!')", updated_at=datetime.utcnow())
        db.session.add_all([c1, c2])

    db.session.commit()

############################
# Minimal environment & ban checks
############################

def environment_check():
    suspicious_names = ["hookfunction", "debug.setupvalue", "hookmetamethod"]
    for name in suspicious_names:
        if name in dir(__builtins__):
            return True
    return False

def is_banned(ip, hwid=None):
    # You could store banned IP/HWID in BlockedIP or a separate table
    b = BlockedIP.query.filter_by(ip_address=ip).first()
    if b:
        return True
    return False

def log_usage(route_name, ip, suspicious=False):
    print(f"[USAGE] route={route_name}, ip={ip}, suspicious={suspicious}")

############################
# Single Big HTML
############################

big_html = r"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8"/>
    <title>EagleHub</title>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <!-- Bootstrap CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css">

    <!-- 1) Icon set (Bootstrap Icons) -->
    <link
      rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css"
    />

    <style>
      body {
        margin: 0;
        background-color: #1f1f1f;
        font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        color: #eee;
      }
      .sidebar {
        position: fixed;
        top: 0; left: 0;
        width: 80px; 
        height: 100vh;
        background-color: #27293d; 
        overflow: hidden;
        transition: width 0.3s;
        z-index: 999;
      }
      .sidebar:hover {
        width: 240px;
      }
      .sidebar ul {
        list-style-type: none;
        padding: 0; margin: 0;
      }
      .sidebar ul li {
        display: flex;
        align-items: center;
        padding: 15px 10px;
        color: #bbb;
        cursor: pointer;
        transition: background-color 0.2s, transform 0.2s;
      }
      .sidebar ul li i {
        font-size: 1.2rem;
        margin-right: 15px;
      }
      .sidebar ul li span {
        white-space: nowrap;
        opacity: 0;
        transition: opacity 0.3s;
      }
      .sidebar:hover ul li span {
        opacity: 1;
      }
      .sidebar ul li:hover {
        background-color: #343759;
        transform: translateX(5px);
      }
      .main-content {
        margin-left: 80px;
        padding: 20px;
        transition: margin-left 0.3s;
      }
      .navbar {
        background-color: #4e1580; /* Purple top bar */
      }
      .navbar-brand {
        font-weight: 600;
      }
      .card {
        background-color: #2a2a2a;
        border: none;
      }
      .card .card-body {
        color: #ddd;
      }
      .table-dark {
        background-color: #2a2a2a;
      }
      .table-dark th,
      .table-dark td {
        border-color: #444;
      }
      .btn-purple {
        background-color: #6a0dad;
        border-color: #6a0dad;
      }
      .btn-purple:hover {
        background-color: #7e39ab;
        border-color: #7e39ab;
      }
    </style>
  </head>
  <body>
    <!-- Left sidebar -->
    <div class="sidebar">
      <ul>
        <li onclick="window.location.href='/'">
          <i class="bi bi-house-fill"></i>
          <span>Dashboard</span>
        </li>
        <li onclick="window.location.href='/scripts/1'">
          <i class="bi bi-code-slash"></i>
          <span>Scripts</span>
        </li>
        <li onclick="window.location.href='/blocked_ips'">
          <i class="bi bi-shield-exclamation"></i>
          <span>Blocked IPs</span>
        </li>
        <li onclick="window.location.href='/killswitch'">
          <i class="bi bi-power"></i>
          <span>Kill Switch</span>
        </li>
        <li onclick="window.location.href='/keys'">
          <i class="bi bi-key"></i>
          <span>Key Manager</span>
        </li>
        <!-- NEW: Loader -->
        <li onclick="window.location.href='/loader_admin'">
          <i class="bi bi-file-earmark-lock"></i>
          <span>Loader</span>
        </li>
      </ul>
    </div>

    <!-- Top nav -->
    <nav class="navbar navbar-expand-lg navbar-dark mb-3">
      <a class="navbar-brand" href="#">EagleHub</a>
      <div class="ml-auto">
        <!-- optional user info or logout button -->
      </div>
    </nav>

    <div class="main-content">
      {% if page == 'dashboard' %}
        {{ dashboard_content|safe }}
      {% else %}
        {% block content %}{% endblock %}
      {% endif %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/js/bootstrap.bundle.min.js"></script>
  </body>
</html>
"""

############################
# Routes
############################

@app.route('/')
def dashboard():
    """Show the main dashboard (stats, charts, projects)."""
    total_executions = 6370
    total_users = 1500
    monthly_executions = 512
    blocked_ips_count = BlockedIP.query.count()

    ks = KillSwitch.query.first()
    kill_switch_active = (ks.active if ks else False)

    # Exec chart data
    exec_chart_data = [random.randint(100, 900) for _ in range(8)]
    rev_rows = Revenue.query.all()
    revenue_chart_data = [r.amount for r in rev_rows]
    monthly_revenue = rev_rows[-1].amount if rev_rows else 0

    projects = Project.query.all()

    dashboard_content = f"""
    <h3>EagleHub Dashboard</h3>
    <!-- You can insert charts or project tables here, like in your original snippet -->
    """
    return render_template_string(
        big_html,
        page='dashboard',
        dashboard_content=dashboard_content
    )

@app.route('/blocked_ips')
def blocked_ips_page():
    blocked_ips = BlockedIP.query.order_by(BlockedIP.created_at.desc()).all()
    # Minimal display
    content = "<h3>Blocked IPs</h3><ul>"
    for b in blocked_ips:
        content += f"<li>{b.ip_address} - {b.reason}</li>"
    content += "</ul>"
    return render_template_string(big_html, page='blocked_ips', blocked_ips=blocked_ips)

@app.route('/killswitch')
def kill_switch_page():
    ks = KillSwitch.query.first()
    content = f"<h3>Kill Switch</h3><p>Status: {'ON' if ks and ks.active else 'OFF'}</p>"
    return render_template_string(big_html, page='killswitch', kill_switch=ks)

@app.route('/scripts/<int:project_id>')
def scripts_page(project_id):
    project = Project.query.get_or_404(project_id)
    scripts = Script.query.filter_by(project_id=project_id).all()
    content = f"<h3>{project.name} Scripts</h3>"
    for s in scripts:
        content += f"<p>{s.name} - v{s.version}</p>"
    return render_template_string(big_html, page='scripts', project=project, scripts=scripts)

@app.route('/keys', methods=['GET','POST'])
def keys_page():
    if request.method == 'POST':
        hwid = request.form.get('hwid') or None
        days = int(request.form.get('days') or 0)
        key_value = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        expires_date = None
        if days > 0:
            expires_date = datetime.utcnow() + timedelta(days=days)
        new_key = Key(value=key_value, hwid=hwid, expires_at=expires_date)
        db.session.add(new_key)
        db.session.commit()
        flash("Key created!", "success")
        return redirect(url_for('keys_page'))

    all_keys = Key.query.order_by(Key.id.desc()).all()
    content = "<h3>Key Manager</h3><ul>"
    for k in all_keys:
        exp_str = k.expires_at.strftime('%Y-%m-%d') if k.expires_at else 'Never'
        content += f"<li>Key {k.value}, HWID={k.hwid}, Expires={exp_str}</li>"
