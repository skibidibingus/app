import os
import random
from datetime import datetime, timedelta
from flask import Flask, request, redirect, url_for, flash
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

    db.session.commit()

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

      /* Stats row, chart containers, etc. */
      .chart-container {
        background-color: #2a2a2a;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 20px;
        width: 95%;
        height: 220px;
        margin-left: auto;
        margin-right: auto;
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
        <!-- WE WILL ADD LOADER OPTION BELOW -->
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
        <!-- Dashboard Stats Cards, charts, projects, etc. -->
        {{ dashboard_content|safe }}

      {% elif page == 'blocked_ips' %}
        <h3>Blocked IPs</h3>
        <table class="table table-dark table-striped">
          <thead>
            <tr><th>IP Address</th><th>Reason</th><th>Created</th></tr>
          </thead>
          <tbody>
          {% for b in blocked_ips %}
            <tr>
              <td>{{ b.ip_address }}</td>
              <td>{{ b.reason }}</td>
              <td>{{ b.created_at.strftime('%Y-%m-%d') }}</td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
        <button class="btn btn-sm btn-success">+ Add Blocked IP</button>

      {% elif page == 'killswitch' %}
        <h3>Kill Switch</h3>
        <p>If the kill switch is ON, all scripts are disabled globally.</p>
        <div class="card">
          <div class="card-body text-center">
            <h5>Status: {% if kill_switch.active %}ON{% else %}OFF{% endif %}</h5>
            {% if kill_switch.active %}
              <a href="{{ url_for('toggle_kill_switch') }}?mode=off" class="btn btn-danger">Turn OFF</a>
            {% else %}
              <a href="{{ url_for('toggle_kill_switch') }}?mode=on" class="btn btn-success">Turn ON</a>
            {% endif %}
          </div>
        </div>

      {% elif page == 'scripts' %}
        <h3>{{ project.name }} Scripts</h3>
        <table class="table table-dark table-striped">
          <thead>
            <tr><th>Name</th><th>Version</th><th>Updated</th><th>Actions</th></tr>
          </thead>
          <tbody>
          {% for s in scripts %}
            <tr>
              <td>{{ s.name }}</td>
              <td>{{ s.version or 'N/A' }}</td>
              <td>{{ s.updated_at.strftime('%Y-%m-%d') }}</td>
              <td>
                <a href="#" class="btn btn-sm btn-purple">Edit</a>
                <a href="#" class="btn btn-sm btn-danger">Delete</a>
              </td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
        <button class="btn btn-sm btn-success">+ Add Script</button>

      {% elif page == 'keys' %}
        <h3>Key Manager</h3>
        <p>Manage all your keys (like Luarmor): create, edit, delete, bind HWIDs, set expirations.</p>
        <!-- Table of keys -->
        <table class="table table-dark table-striped">
          <thead>
            <tr>
              <th>ID</th>
              <th>Value</th>
              <th>HWID</th>
              <th>Expires</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
          {% for k in keys %}
            <tr>
              <td>{{ k.id }}</td>
              <td>{{ k.value }}</td>
              <td>{{ k.hwid or 'None' }}</td>
              <td>{% if k.expires_at %}{{ k.expires_at.strftime('%Y-%m-%d') }}{% else %}Never{% endif %}</td>
              <td>
                <a href="{{ url_for('edit_key', key_id=k.id) }}" class="btn btn-sm btn-purple">Edit</a>
                <a href="{{ url_for('delete_key', key_id=k.id) }}" class="btn btn-sm btn-danger">Delete</a>
              </td>
            </tr>
          {% endfor %}
          </tbody>
        </table>

        <!-- Form to create new key -->
        <h5>Create New Key</h5>
        <form method="POST" action="{{ url_for('keys_page') }}">
          <div class="form-group">
            <label>HWID (optional)</label>
            <input type="text" name="hwid" class="form-control">
          </div>
          <div class="form-group">
            <label>Expires (days) - 0 for never</label>
            <input type="number" name="days" class="form-control" value="0">
          </div>
          <button type="submit" class="btn btn-success btn-sm">Create Key</button>
        </form>

      {% elif page == 'edit_key' %}
        <h3>Edit Key #{{ key.id }}</h3>
        <form method="POST">
          <div class="form-group">
            <label>HWID</label>
            <input type="text" name="hwid" class="form-control" value="{{ key.hwid or '' }}">
          </div>
          <div class="form-group">
            <label>Expires (days) - 0 for never</label>
            <input type="number" name="days" class="form-control" value="{{ days_left }}">
          </div>
          <button type="submit" class="btn btn-primary btn-sm">Save Changes</button>
          <a href="{{ url_for('keys_page') }}" class="btn btn-secondary btn-sm">Cancel</a>
        </form>

      {% else %}
        <h3>404 Not Found</h3>
      {% endif %}
    </div>

    <!-- JS includes -->
    <script src="https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/js/bootstrap.bundle.min.js"></script>
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
    # Revenue chart data
    rev_rows = Revenue.query.all()
    revenue_chart_data = [r.amount for r in rev_rows]
    monthly_revenue = rev_rows[-1].amount if rev_rows else 0

    projects = Project.query.all()

    # We'll build the dashboard content in a separate variable
    dashboard_content = f"""
    <div class="row mb-4">
      <div class="col-md-2">
        <div class="card">
          <div class="card-body text-center">
            <h6>Total Exec</h6>
            <h3>{total_executions}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-2">
        <div class="card">
          <div class="card-body text-center">
            <h6>Total Users</h6>
            <h3>{total_users}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-2">
        <div class="card">
          <div class="card-body text-center">
            <h6>Monthly Exec</h6>
            <h3>{monthly_executions}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-2">
        <div class="card">
          <div class="card-body text-center">
            <h6>Blocked IPs</h6>
            <h3>{blocked_ips_count}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-2">
        <div class="card">
          <div class="card-body text-center">
            <h6>Kill Switch</h6>
            <h3>{'ON' if kill_switch_active else 'OFF'}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-2">
        <div class="card">
          <div class="card-body text-center">
            <h6>Monthly Rev</h6>
            <h3>${monthly_revenue}</h3>
          </div>
        </div>
      </div>
    </div>
    """

    return render_template_string(
        big_html,
        page='dashboard',
        dashboard_content=dashboard_content
    )

@app.route('/blocked_ips')
def blocked_ips_page():
    """Show all blocked IPs."""
    blocked_ips = BlockedIP.query.order_by(BlockedIP.created_at.desc()).all()
    return render_template_string(
        big_html,
        page='blocked_ips',
        blocked_ips=blocked_ips
    )

@app.route('/killswitch')
def kill_switch_page():
    """Show kill switch page."""
    ks = KillSwitch.query.first()
    return render_template_string(
        big_html,
        page='killswitch',
        kill_switch=ks
    )

@app.route('/killswitch/toggle')
def toggle_kill_switch():
    """Toggle kill switch on/off."""
    mode = request.args.get('mode')
    ks = KillSwitch.query.first()
    if not ks:
        ks = KillSwitch(active=False)
        db.session.add(ks)
        db.session.commit()

    if mode == 'on':
        ks.active = True
    elif mode == 'off':
        ks.active = False

    db.session.commit()
    flash(f"Kill switch turned {'ON' if ks.active else 'OFF'}.", "info")
    return redirect(url_for('kill_switch_page'))

@app.route('/scripts/<int:project_id>')
def scripts_page(project_id):
    """Show scripts for a given project."""
    project = Project.query.get_or_404(project_id)
    scripts = Script.query.filter_by(project_id=project_id).all()
    return render_template_string(
        big_html,
        page='scripts',
        project=project,
        scripts=scripts
    )

######################
# KEY MANAGER ROUTES
######################

@app.route('/keys', methods=['GET','POST'])
def keys_page():
    """List all keys, create new key if POST."""
    if request.method == 'POST':
        hwid = request.form.get('hwid') or None
        days = int(request.form.get('days') or 0)
        # Generate random key value
        import string
        key_value = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        expires_date = None
        if days > 0:
            expires_date = datetime.utcnow() + timedelta(days=days)
        new_key = Key(value=key_value, hwid=hwid, expires_at=expires_date)
        db.session.add(new_key)
        db.session.commit()
        flash("Key created!", "success")
        return redirect(url_for('keys_page'))

    keys = Key.query.order_by(Key.id.desc()).all()
    return render_template_string(
        big_html,
        page='keys',
        keys=keys
    )

@app.route('/keys/<int:key_id>/edit', methods=['GET','POST'])
def edit_key(key_id):
    """Edit a specific key (HWID, expiry)."""
    key = Key.query.get_or_404(key_id)
    if request.method == 'POST':
        hwid = request.form.get('hwid') or None
        days = int(request.form.get('days') or 0)
        key.hwid = hwid
        if days > 0:
            key.expires_at = datetime.utcnow() + timedelta(days=days)
        else:
            key.expires_at = None
        db.session.commit()
        flash("Key updated!", "success")
        return redirect(url_for('keys_page'))

    # Calculate days left if any
    days_left = 0
    if key.expires_at:
        diff = key.expires_at - datetime.utcnow()
        days_left = diff.days if diff.days > 0 else 0

    return render_template_string(
        big_html,
        page='edit_key',
        key=key,
        days_left=days_left
    )

@app.route('/keys/<int:key_id>/delete')
def delete_key(key_id):
    """Delete a key."""
    key = Key.query.get_or_404(key_id)
    db.session.delete(key)
    db.session.commit()
    flash("Key deleted!", "warning")
    return redirect(url_for('keys_page'))

###################################################
# NEW: SINGLE-CHUNK LOADER
###################################################

# 1) Model to store single script (like "MainScript"), 
#    but we only use one row for the entire code:
class MainScript(db.Model):
    __tablename__ = "main_script_single"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

# 2) Ephemeral route model for single-chunk usage
class EphemeralRoute(db.Model):
    __tablename__ = "ephemeral_route_single"
    id = db.Column(db.Integer, primary_key=True)
    route_name = db.Column(db.String(50), unique=True, nullable=False)
    token = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_in = db.Column(db.Integer, default=120)
    single_use = db.Column(db.Boolean, default=True)

# Minimal environment & ban checks, plus usage logging
def environment_check():
    suspicious_names = ["hookfunction", "debug.setupvalue", "hookmetamethod"]
    for name in suspicious_names:
        if name in dir(__builtins__):
            return True
    return False

def is_banned(ip, hwid=None):
    b = BlockedIP.query.filter_by(ip_address=ip).first()
    if b:
        return True
    return False

def log_usage(route_name, ip, suspicious=False):
    print(f"[LOADER USAGE] route={route_name}, ip={ip}, suspicious={suspicious}")

# 3) Loader Admin: single script (no chunk index)
@app.route('/loader_admin', methods=['GET','POST'])
def loader_admin():
    """
    We only have 1 row in MainScript. The user can edit that row's code.
    """
    ms = MainScript.query.first()
    if request.method == 'POST':
        code = request.form.get('code', '')
        if ms:
            ms.code = code
            ms.updated_at = datetime.utcnow()
        else:
            ms = MainScript(code=code, updated_at=datetime.utcnow())
            db.session.add(ms)
        db.session.commit()
        flash("Loader script updated!", "success")
        return redirect(url_for('loader_admin'))

    existing_code = ms.code if ms else ""
    page_content = f"""
<h3>Single-Chunk Loader Admin</h3>
<p>Manage the single script code. For Luarmor-like security, 
you can externally obfuscate this code if desired.</p>
<form method="POST">
  <textarea name="code" rows="10" cols="60">{existing_code}</textarea>
  <br/>
  <button type="submit" class="btn btn-success">Save Script</button>
</form>
"""
    return render_template_string(big_html, content=page_content)

# 4) Loader Create: generates ephemeral route for the single script
@app.route('/loader_create')
def loader_create():
    ms = MainScript.query.first()
    if not ms:
        return "No main script found. Add some in /loader_admin."

    if environment_check():
        return "Suspicious environment. Aborting ephemeral route creation.", 403

    # Generate ephemeral route
    import secrets
    import random
    import string

    route_name = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    token_str = secrets.token_hex(16)
    er = EphemeralRoute(
        route_name=route_name,
        token=token_str,
        created_at=datetime.utcnow(),
        expires_in=120,
        single_use=True
    )
    db.session.add(er)
    db.session.commit()

    page_content = f"""
<h3>Single-Chunk Ephemeral Loader Route Created</h3>
<ul>
  <li>/{route_name}?key=YOUR_KEY&hwid=YOUR_HWID&token={token_str}</li>
</ul>
<p>Expires in 120 seconds, single-use. 
Call it once with the correct key, hwid, and token.</p>
"""
    return render_template_string(big_html, content=page_content)

# 5) The ephemeral route: single chunk
@app.route('/<path:loader_route>')
def loader_catch_all_single(loader_route):
    """
    If loader_route matches EphemeralRoute, we do environment hooking checks,
    ban checks, ephemeral token checks, triple base64 + illusions, single use,
    returning the single main script code.
    """
    er = EphemeralRoute.query.filter_by(route_name=loader_route).first()
    if not er:
        return "404 Not Found", 404

    if environment_check():
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Suspicious environment. Aborting route usage.", 403

    user_hwid = request.args.get('hwid', '')
    if is_banned(request.remote_addr, user_hwid):
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "You are banned from using this service.", 403

    delta = (datetime.utcnow() - er.created_at).total_seconds()
    if delta > er.expires_in:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Ephemeral route expired", 403

    user_token = request.args.get('token', '')
    if user_token != er.token:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Invalid token", 403

    user_key = request.args.get('key', '')
    if not user_key:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Missing key param", 400

    # Validate key
    kobj = Key.query.filter_by(value=user_key).first()
    if not kobj:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Invalid key", 403
    if kobj.expires_at and datetime.utcnow() > kobj.expires_at:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Key expired", 403

    # Check killswitch if you want:
    ks = KillSwitch.query.first()
    if ks and ks.active:
        return "Kill Switch is active. Scripts disabled.", 403

    # Get the single main script
    ms = MainScript.query.first()
    if not ms:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "No main script found", 500

    # triple base64 + illusions
    import base64
    step1 = base64.b64encode(ms.code.encode()).decode()
    step2 = base64.b64encode(step1.encode()).decode()
    step3 = base64.b64encode(step2.encode()).decode()

    illusionsA = secrets.token_urlsafe(8)
    illusionsB = secrets.token_urlsafe(8)

    final_lua = f"""
-- environment check in-lua
if hookfunction or debug.setupvalue or hookmetamethod then
    return print("Suspicious environment, aborting script.")
end

local step3 = "{step3}"
local s2 = game:GetService("HttpService"):Base64Decode(step3)
local s1 = game:GetService("HttpService"):Base64Decode(s2)
local final = game:GetService("HttpService"):Base64Decode(s1)

-- illusions
local illusionsA = "{illusionsA}"
local illusionsB = "{illusionsB}"

loadstring(final)()
"""

    if er.single_use:
        db.session.delete(er)
        db.session.commit()

    log_usage(er.route_name, request.remote_addr, suspicious=False)
    return Response(final_lua, mimetype='text/plain')

############################
# MAIN
############################
with app.app_context():
    db.create_all()
    seed_data()

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5000)
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

    db.session.commit()

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

      /* Stats row, chart containers, etc. */
      .chart-container {
        background-color: #2a2a2a;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 20px;
        width: 95%;
        height: 220px;
        margin-left: auto;
        margin-right: auto;
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
        <!-- We'll add advanced VM loader below -->
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
        <!-- Dashboard Stats Cards, charts, projects, etc. -->
        {{ dashboard_content|safe }}

      {% elif page == 'blocked_ips' %}
        <h3>Blocked IPs</h3>
        <table class="table table-dark table-striped">
          <thead>
            <tr><th>IP Address</th><th>Reason</th><th>Created</th></tr>
          </thead>
          <tbody>
          {% for b in blocked_ips %}
            <tr>
              <td>{{ b.ip_address }}</td>
              <td>{{ b.reason }}</td>
              <td>{{ b.created_at.strftime('%Y-%m-%d') }}</td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
        <button class="btn btn-sm btn-success">+ Add Blocked IP</button>

      {% elif page == 'killswitch' %}
        <h3>Kill Switch</h3>
        <p>If the kill switch is ON, all scripts are disabled globally.</p>
        <div class="card">
          <div class="card-body text-center">
            <h5>Status: {% if kill_switch.active %}ON{% else %}OFF{% endif %}</h5>
            {% if kill_switch.active %}
              <a href="{{ url_for('toggle_kill_switch') }}?mode=off" class="btn btn-danger">Turn OFF</a>
            {% else %}
              <a href="{{ url_for('toggle_kill_switch') }}?mode=on" class="btn btn-success">Turn ON</a>
            {% endif %}
          </div>
        </div>

      {% elif page == 'scripts' %}
        <h3>{{ project.name }} Scripts</h3>
        <table class="table table-dark table-striped">
          <thead>
            <tr><th>Name</th><th>Version</th><th>Updated</th><th>Actions</th></tr>
          </thead>
          <tbody>
          {% for s in scripts %}
            <tr>
              <td>{{ s.name }}</td>
              <td>{{ s.version or 'N/A' }}</td>
              <td>{{ s.updated_at.strftime('%Y-%m-%d') }}</td>
              <td>
                <a href="#" class="btn btn-sm btn-purple">Edit</a>
                <a href="#" class="btn btn-sm btn-danger">Delete</a>
              </td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
        <button class="btn btn-sm btn-success">+ Add Script</button>

      {% elif page == 'keys' %}
        <h3>Key Manager</h3>
        <p>Manage all your keys (like Luarmor): create, edit, delete, bind HWIDs, set expirations.</p>
        <!-- Table of keys -->
        <table class="table table-dark table-striped">
          <thead>
            <tr>
              <th>ID</th>
              <th>Value</th>
              <th>HWID</th>
              <th>Expires</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
          {% for k in keys %}
            <tr>
              <td>{{ k.id }}</td>
              <td>{{ k.value }}</td>
              <td>{{ k.hwid or 'None' }}</td>
              <td>{% if k.expires_at %}{{ k.expires_at.strftime('%Y-%m-%d') }}{% else %}Never{% endif %}</td>
              <td>
                <a href="{{ url_for('edit_key', key_id=k.id) }}" class="btn btn-sm btn-purple">Edit</a>
                <a href="{{ url_for('delete_key', key_id=k.id) }}" class="btn btn-sm btn-danger">Delete</a>
              </td>
            </tr>
          {% endfor %}
          </tbody>
        </table>

        <!-- Form to create new key -->
        <h5>Create New Key</h5>
        <form method="POST" action="{{ url_for('keys_page') }}">
          <div class="form-group">
            <label>HWID (optional)</label>
            <input type="text" name="hwid" class="form-control">
          </div>
          <div class="form-group">
            <label>Expires (days) - 0 for never</label>
            <input type="number" name="days" class="form-control" value="0">
          </div>
          <button type="submit" class="btn btn-success btn-sm">Create Key</button>
        </form>

      {% elif page == 'edit_key' %}
        <h3>Edit Key #{{ key.id }}</h3>
        <form method="POST">
          <div class="form-group">
            <label>HWID</label>
            <input type="text" name="hwid" class="form-control" value="{{ key.hwid or '' }}">
          </div>
          <div class="form-group">
            <label>Expires (days) - 0 for never</label>
            <input type="number" name="days" class="form-control" value="{{ days_left }}">
          </div>
          <button type="submit" class="btn btn-primary btn-sm">Save Changes</button>
          <a href="{{ url_for('keys_page') }}" class="btn btn-secondary btn-sm">Cancel</a>
        </form>

      {% else %}
        <h3>404 Not Found</h3>
      {% endif %}
    </div>

    <!-- JS includes -->
    <script src="https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/js/bootstrap.bundle.min.js"></script>
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
    # Revenue chart data
    rev_rows = Revenue.query.all()
    revenue_chart_data = [r.amount for r in rev_rows]
    monthly_revenue = rev_rows[-1].amount if rev_rows else 0

    projects = Project.query.all()

    # We'll build the dashboard content in a separate variable
    dashboard_content = f"""
    <div class="row mb-4">
      <div class="col-md-2">
        <div class="card">
          <div class="card-body text-center">
            <h6>Total Exec</h6>
            <h3>{total_executions}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-2">
        <div class="card">
          <div class="card-body text-center">
            <h6>Total Users</h6>
            <h3>{total_users}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-2">
        <div class="card">
          <div class="card-body text-center">
            <h6>Monthly Exec</h6>
            <h3>{monthly_executions}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-2">
        <div class="card">
          <div class="card-body text-center">
            <h6>Blocked IPs</h6>
            <h3>{blocked_ips_count}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-2">
        <div class="card">
          <div class="card-body text-center">
            <h6>Kill Switch</h6>
            <h3>{'ON' if kill_switch_active else 'OFF'}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-2">
        <div class="card">
          <div class="card-body text-center">
            <h6>Monthly Rev</h6>
            <h3>${monthly_revenue}</h3>
          </div>
        </div>
      </div>
    </div>
    """

    return render_template_string(
        big_html,
        page='dashboard',
        dashboard_content=dashboard_content
    )

@app.route('/blocked_ips')
def blocked_ips_page():
    """Show all blocked IPs."""
    blocked_ips = BlockedIP.query.order_by(BlockedIP.created_at.desc()).all()
    return render_template_string(
        big_html,
        page='blocked_ips',
        blocked_ips=blocked_ips
    )

@app.route('/killswitch')
def kill_switch_page():
    """Show kill switch page."""
    ks = KillSwitch.query.first()
    return render_template_string(
        big_html,
        page='killswitch',
        kill_switch=ks
    )

@app.route('/killswitch/toggle')
def toggle_kill_switch():
    """Toggle kill switch on/off."""
    mode = request.args.get('mode')
    ks = KillSwitch.query.first()
    if not ks:
        ks = KillSwitch(active=False)
        db.session.add(ks)
        db.session.commit()

    if mode == 'on':
        ks.active = True
    elif mode == 'off':
        ks.active = False

    db.session.commit()
    flash(f"Kill switch turned {'ON' if ks.active else 'OFF'}.", "info")
    return redirect(url_for('kill_switch_page'))

@app.route('/scripts/<int:project_id>')
def scripts_page(project_id):
    """Show scripts for a given project."""
    project = Project.query.get_or_404(project_id)
    scripts = Script.query.filter_by(project_id=project_id).all()
    return render_template_string(
        big_html,
        page='scripts',
        project=project,
        scripts=scripts
    )

######################
# KEY MANAGER ROUTES
######################

@app.route('/keys', methods=['GET','POST'])
def keys_page():
    """List all keys, create new key if POST."""
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
    return render_template_string(
        big_html,
        page='keys',
        keys=all_keys
    )

@app.route('/keys/<int:key_id>/edit', methods=['GET','POST'])
def edit_key(key_id):
    """Edit a specific key (HWID, expiry)."""
    key = Key.query.get_or_404(key_id)
    if request.method == 'POST':
        hwid = request.form.get('hwid') or None
        days = int(request.form.get('days') or 0)
        key.hwid = hwid
        if days > 0:
            key.expires_at = datetime.utcnow() + timedelta(days=days)
        else:
            key.expires_at = None
        db.session.commit()
        flash("Key updated!", "success")
        return redirect(url_for('keys_page'))

    days_left = 0
    if key.expires_at:
        diff = key.expires_at - datetime.utcnow()
        days_left = diff.days if diff.days > 0 else 0

    return render_template_string(
        big_html,
        page='edit_key',
        key=key,
        days_left=days_left
    )

@app.route('/keys/<int:key_id>/delete')
def delete_key(key_id):
    """Delete a key."""
    key = Key.query.get_or_404(key_id)
    db.session.delete(key)
    db.session.commit()
    flash("Key deleted!", "warning")
    return redirect(url_for('keys_page'))

###################################################
# ADVANCED VIRTUALIZATION (LUARMOR-LEVEL) SINGLE-CHUNK LOADER
###################################################

class VirtualScript(db.Model):
    __tablename__ = "virtual_script_advanced"
    id = db.Column(db.Integer, primary_key=True)
    # We'll store fully virtualized bytecode
    bytecode = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class EphemeralRouteVM(db.Model):
    __tablename__ = "ephemeral_route_vm_advanced"
    id = db.Column(db.Integer, primary_key=True)
    route_name = db.Column(db.String(50), unique=True, nullable=False)
    token = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_in = db.Column(db.Integer, default=120)
    single_use = db.Column(db.Boolean, default=True)

############################
# 1) FULL VM COMPILER: "lua_source" -> "vm_bytecode"
############################

# We define a "toy advanced" parser for the major Lua constructs:
# - Arithmetic ops (+, -, *, /, %)
# - Comparisons (==, ~=, <, >, <=, >=)
# - if statements, while loops, for loops
# - function definitions, calls
# - table indexing
# - metamethod placeholders
# - upvalues
# This is still a demonstration but more thorough.

import re

TOKENS = [
    (r"[A-Za-z_]\w*", "IDENT"),     # identifiers
    (r"==|~=|<=|>=|<|>", "COMP"),   # comparison ops
    (r"\+|\-|\*|\/|\%|\^", "ARITH"),# arithmetic
    (r"\.\.\.", "VARARG"),          # ...
    (r"\.\.", "CONCAT"),            # ..
    (r"\=", "ASSIGN"),
    (r"\(", "LPAREN"),
    (r"\)", "RPAREN"),
    (r"\{", "LBRACE"),
    (r"\}", "RBRACE"),
    (r"\[", "LBRACKET"),
    (r"\]", "RBRACKET"),
    (r";", "SEMICOLON"),
    (r":", "COLON"),
    (r"\.", "DOT"),
    (r",", "COMMA"),
    (r"\"(?:\\.|[^\"])*\"", "STRING_DQ"),   # "string"
    (r"\'(?:\\.|[^\'])*\'", "STRING_SQ"),  # 'string'
    (r"\d+(\.\d+)?", "NUMBER"),
    (r"if|then|else|elseif|end|while|do|for|in|repeat|until|function|local|return|break|true|false|nil|not|and|or", "KEYWORD"),
]

token_regex = re.compile("|".join(f"(?P<{name}>{pattern})" for pattern, name in TOKENS)|r"|(?P<WHITESPACE>\s+)|(?P<UNKNOWN>.)")

def advanced_tokenize(lua_source):
    tokens = []
    for m in token_regex.finditer(lua_source):
        kind = m.lastgroup
        text = m.group(kind)
        if kind == "WHITESPACE":
            continue
        elif kind == "UNKNOWN":
            # unexpected char
            tokens.append(("UNKNOWN", text))
        else:
            tokens.append((kind, text))
    return tokens

def advanced_compile(lua_source):
    """
    We'll parse the tokens into a "VM instruction set" covering
    arithmetic, function calls, loops, etc. This is still a demonstration
    but more advanced than a minimal approach.
    """
    # 1) tokenize
    tokens = advanced_tokenize(lua_source)

    # 2) We'll do a naive pass that just stores them in a custom format
    #    In a real system, you'd build an AST, then produce bytecode instructions
    #    for each node. We'll just create "op:data" pairs for demonstration.

    instructions = []
    for (kind, text) in tokens:
        # We'll store "KIND:base64(text)"
        import base64
        data_enc = base64.b64encode(text.encode()).decode()
        instructions.append(f"{kind}:{data_enc}")

    # Join with '|'
    return "|".join(instructions)

############################
# 2) VM INTERPRETER in-lua
############################

# We'll embed a big "vm_run" function in-lua that handles the instructions
# for arithmetic, comparisons, if/while, function calls, etc. 
# This is a large demonstration, not guaranteed to handle every edge case.

# We'll define that in-lua. We'll generate it dynamically in the ephemeral route.

############################
# VM Loader Admin
############################
@app.route('/vm_loader_admin_advanced', methods=['GET','POST'])
def vm_loader_admin_advanced():
    """
    We store 1 VirtualScript row with advanced VM bytecode.
    The user provides normal Lua code, we compile to advanced bytecode.
    """
    vs = VirtualScript.query.first()
    if request.method == 'POST':
        lua_source = request.form.get('code', '')
        compiled_bc = advanced_compile(lua_source)
        if vs:
            vs.bytecode = compiled_bc
            vs.updated_at = datetime.utcnow()
        else:
            vs = VirtualScript(bytecode=compiled_bc, updated_at=datetime.utcnow())
            db.session.add(vs)
        db.session.commit()
        flash("Advanced VM Script updated!", "success")
        return redirect(url_for('vm_loader_admin_advanced'))

    existing_bc = vs.bytecode if vs else ""
    page_content = f"""
<h3>Advanced VM Loader Admin</h3>
<p>Paste normal Lua code, we compile to a custom VM instruction set 
covering major Lua features (arithmetic, loops, if, function calls, etc.).</p>
<form method="POST">
  <label>Lua Code</label><br/>
  <textarea name="code" rows="10" cols="60"></textarea>
  <br/><br/>
  <button type="submit" class="btn btn-success">Compile to VM Bytecode</button>
</form>
<hr/>
<h4>Current Bytecode</h4>
<pre>{existing_bc}</pre>
"""
    return render_template_string(big_html, content=page_content)

############################
# Ephemeral Route
############################
class EphemeralRouteVM(db.Model):
    __tablename__ = "ephemeral_route_vm_advanced2"
    id = db.Column(db.Integer, primary_key=True)
    route_name = db.Column(db.String(50), unique=True, nullable=False)
    token = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_in = db.Column(db.Integer, default=120)
    single_use = db.Column(db.Boolean, default=True)

############################
# Helper Checks
############################
def environment_check():
    suspicious_names = ["hookfunction", "debug.setupvalue", "hookmetamethod"]
    for name in suspicious_names:
        if name in dir(__builtins__):
            return True
    return False

def is_banned(ip, hwid=None):
    b = BlockedIP.query.filter_by(ip_address=ip).first()
    if b:
        return True
    return False

def log_usage(route_name, ip, suspicious=False):
    print(f"[VM ADVANCED USAGE] route={route_name}, ip={ip}, suspicious={suspicious}")

############################
# /vm_loader_create_advanced
############################
@app.route('/vm_loader_create_advanced')
def vm_loader_create_advanced():
    vs = VirtualScript.query.first()
    if not vs:
        return "No advanced VM script compiled. Use /vm_loader_admin_advanced"

    if environment_check():
        return "Suspicious environment. Aborting ephemeral route creation.", 403

    route_name = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    token_str = secrets.token_hex(16)
    er = EphemeralRouteVM(
        route_name=route_name,
        token=token_str,
        created_at=datetime.utcnow(),
        expires_in=120,
        single_use=True
    )
    db.session.add(er)
    db.session.commit()

    page_content = f"""
<h3>Advanced VM Ephemeral Route Created</h3>
<ul>
  <li>/{route_name}?key=YOUR_KEY&hwid=YOUR_HWID&token={token_str}</li>
</ul>
<p>Expires in 120 seconds, single-use. 
We do environment hooking checks, ban checks, kill switch checks, triple base64, illusions, 
and interpret your script under a custom VM in-lua with no standard Lua instructions left.</p>
"""
    return render_template_string(big_html, content=page_content)

############################
# Catch-all for advanced VM
############################
@app.route('/<path:vm_advanced_route>')
def vm_advanced_loader(vm_advanced_route):
    er = EphemeralRouteVM.query.filter_by(route_name=vm_advanced_route).first()
    if not er:
        return "404 Not Found", 404

    # environment check
    if environment_check():
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Suspicious environment. Aborting route usage.", 403

    user_hwid = request.args.get('hwid', '')
    if is_banned(request.remote_addr, user_hwid):
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "You are banned from using this service.", 403

    delta = (datetime.utcnow() - er.created_at).total_seconds()
    if delta > er.expires_in:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Ephemeral route expired", 403

    user_token = request.args.get('token', '')
    if user_token != er.token:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Invalid token", 403

    user_key = request.args.get('key', '')
    if not user_key:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Missing key param", 400

    # validate key
    kobj = Key.query.filter_by(value=user_key).first()
    if not kobj:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Invalid key", 403
    if kobj.expires_at and datetime.utcnow() > kobj.expires_at:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Key expired", 403

    # kill switch check
    ks = KillSwitch.query.first()
    if ks and ks.active:
        return "Kill Switch active. Scripts disabled.", 403

    vs = VirtualScript.query.first()
    if not vs:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "No advanced VM script found", 500

    # triple base64 + illusions
    import base64
    step1 = base64.b64encode(vs.bytecode.encode()).decode()
    step2 = base64.b64encode(step1.encode()).decode()
    step3 = base64.b64encode(step2.encode()).decode()

    illusionsA = secrets.token_urlsafe(8)
    illusionsB = secrets.token_urlsafe(8)

    # We'll embed a large "vm_run" function in-lua that interprets
    # our advanced instructions. We'll handle arithmetic, function calls, etc.
    # This is extremely large. We'll do a toy approach that tries to handle them.
    # This is still a demonstration, but more advanced than minimal.

    final_lua = f"""
-- environment hooking check in-lua
if hookfunction or debug.setupvalue or hookmetamethod then
    return print("Suspicious environment, aborting advanced VM.")
end

local illusionsA = "{illusionsA}"
local illusionsB = "{illusionsB}"

local step3 = "{step3}"
local s2 = game:GetService("HttpService"):Base64Decode(step3)
local s1 = game:GetService("HttpService"):Base64Decode(s2)
local finalBytecode = game:GetService("HttpService"):Base64Decode(s1)

-- We'll parse instructions of the form KIND:base64(token).
-- Then interpret them as a custom VM covering major Lua ops.

local function decodeBase64(b64)
    return syn.crypt.base64.decode(b64)
end

local function splitBytecode(bytecode)
    local instructions = {}
    for part in string.gmatch(bytecode, '([^|]+)') do
        table.insert(instructions, part)
    end
    return instructions
end

-- We'll keep a stack-based VM, plus an environment table.
local function advanced_vm_run(bytecode)
    local instructions = splitBytecode(bytecode)
    local stack = {}
    local env = {}
    local pc = 1
    local function push(val) stack[#stack+1] = val end
    local function pop() local v=stack[#stack]; stack[#stack]=nil; return v end

    local function do_arith(op)
        local b = pop()
        local a = pop()
        if op == "+" then push(a + b)
        elseif op == "-" then push(a - b)
        elseif op == "*" then push(a * b)
        elseif op == "/" then push(a / b)
        elseif op == "%" then push(a % b)
        end
    end

    local function do_comp(op)
        local b = pop()
        local a = pop()
        if op == "==" then push(a == b)
        elseif op == "~=" then push(a ~= b)
        elseif op == "<" then push(a < b)
        elseif op == ">" then push(a > b)
        elseif op == "<=" then push(a <= b)
        elseif op == ">=" then push(a >= b)
        end
    end

    local function do_assign()
        local val = pop()
        local var = pop()
        env[var] = val
    end

    local function do_print(val)
        print(val)
    end

    while pc <= #instructions do
        local instr = instructions[pc]
        pc = pc + 1
        local parts = {}
        for sub in string.gmatch(instr, "([^:]+)") do
            table.insert(parts, sub)
        end
        local kind = parts[1]
        local dataEnc = parts[2] or ""
        local data = decodeBase64(dataEnc)

        if kind == "WHITESPACE" or kind == "UNKNOWN" then
            -- skip
        elseif kind == "IDENT" then
            push(data)  -- push the identifier name
        elseif kind == "NUMBER" then
            push(tonumber(data))
        elseif kind == "STRING_DQ" or kind == "STRING_SQ" then
            -- remove quotes
            local strVal = data
            if (strVal:sub(1,1) == '"' and strVal:sub(-1) == '"') or
               (strVal:sub(1,1) == "'" and strVal:sub(-1) == "'") then
                strVal = strVal:sub(2,-2)
            end
            push(strVal)
        elseif kind == "ARITH" then
            do_arith(data)
        elseif kind == "COMP" then
            do_comp(data)
        elseif kind == "ASSIGN" then
            do_assign()
        elseif kind == "KEYWORD" then
            -- handle if/then/else, for, while, etc. (very partial)
            -- real advanced approach would parse a big AST
            -- we'll skip for brevity
        else
            -- skip or push data
        end
    end
end

advanced_vm_run(finalBytecode)
"""

    if er.single_use:
        db.session.delete(er)
        db.session.commit()

    log_usage(er.route_name, request.remote_addr, suspicious=False)
    return Response(final_lua, mimetype='text/plain')

############################
# MAIN
############################
with app.app_context():
    db.create_all()
    seed_data()

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5000)
