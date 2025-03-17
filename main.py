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
# NEW MODELS for Loader
############################

class MainScript(db.Model):
    """
    Multi-chunk script storage.
    chunk_index=1,2,...
    code=the raw Lua script chunk
    """
    id = db.Column(db.Integer, primary_key=True)
    chunk_index = db.Column(db.Integer, default=1)
    code = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class EphemeralRoute(db.Model):
    """
    Short-lived route for each chunk with Luarmor-like ephemeral tokens.
    route_name = random route string
    token = random hex
    chunk_index=which chunk
    single_use=delete after usage
    """
    __tablename__ = "ephemeral_routes_v2"  # rename to avoid conflict if needed
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
        import random
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug"]
        for m in months:
            r = Revenue(month=m, amount=random.randint(300, 2000))
            db.session.add(r)

    # Sample keys
    if not Key.query.first():
        k1 = Key(value="ABCDEF1234567890", hwid=None, expires_at=None)
        k2 = Key(value="HELLO987654321", hwid="HWID-TEST", expires_at=datetime.utcnow()+timedelta(days=7))
        db.session.add_all([k1, k2])

    # Sample main script chunks if none exist
    if not MainScript.query.first():
        c1 = MainScript(chunk_index=1, code="print('Hello from chunk #1!')", updated_at=datetime.utcnow())
        c2 = MainScript(chunk_index=2, code="print('Hello from chunk #2!')", updated_at=datetime.utcnow())
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
    # If you want to store banned IP or HWID in BlockedIP
    # adapt your logic here
    b = BlockedIP.query.filter_by(ip_address=ip).first()
    if b:
        return True
    return False

def log_usage(route_name, ip, suspicious=False):
    print(f"[USAGE] route={route_name}, ip={ip}, suspicious={suspicious}")

############################
# big_html
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
        background-color: #4e1580; 
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
        <!-- NEW LOADER OPTION -->
        <li onclick="window.location.href='/loader_admin'">
          <i class="bi bi-file-earmark-lock"></i>
          <span>Loader</span>
        </li>
      </ul>
    </div>

    <nav class="navbar navbar-expand-lg navbar-dark mb-3">
      <a class="navbar-brand" href="#">EagleHub</a>
      <div class="ml-auto"></div>
    </nav>

    <div class="main-content">
      {% block content %}{% endblock %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/js/bootstrap.bundle.min.js"></script>
  </body>
</html>
"""

############################
# Dashboard route
############################
@app.route('/')
def dashboard():
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

    # Insert charts or more content here if desired
    return render_template_string(
        big_html,
        content=dashboard_content
    )

############################
# /blocked_ips, /killswitch, /scripts, /keys
# (unchanged from your code)
############################

@app.route('/scripts/<int:project_id>')
def scripts_page(project_id):
    project = Project.query.get_or_404(project_id)
    scripts = Script.query.filter_by(project_id=project_id).all()
    # Reuse big_html
    page_content = f"<h3>{project.name} Scripts</h3>"
    page_content += "<table class='table table-dark table-striped'><thead><tr><th>Name</th><th>Version</th><th>Updated</th></tr></thead><tbody>"
    for s in scripts:
        page_content += f"<tr><td>{s.name}</td><td>{s.version}</td><td>{s.updated_at.strftime('%Y-%m-%d')}</td></tr>"
    page_content += "</tbody></table>"
    return render_template_string(big_html, content=page_content)

@app.route('/killswitch')
def kill_switch_page():
    ks = KillSwitch.query.first()
    page_content = "<h3>Kill Switch</h3>"
    page_content += f"<p>Status: {'ON' if ks and ks.active else 'OFF'}</p>"
    return render_template_string(big_html, content=page_content)

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
    page_content = "<h3>Key Manager</h3>"
    page_content += "<table class='table table-dark table-striped'><thead><tr><th>ID</th><th>Value</th><th>HWID</th><th>Expires</th></tr></thead><tbody>"
    for k in all_keys:
        exp_str = k.expires_at.strftime('%Y-%m-%d') if k.expires_at else 'Never'
        page_content += f"<tr><td>{k.id}</td><td>{k.value}</td><td>{k.hwid or 'None'}</td><td>{exp_str}</td></tr>"
    page_content += "</tbody></table>"
    page_content += """
<form method="POST">
  <label>HWID (optional)</label>
  <input type="text" name="hwid" class="form-control" />
  <label>Expires (days) - 0=never</label>
  <input type="number" name="days" class="form-control" value="0" />
  <button type="submit" class="btn btn-success">Create Key</button>
</form>
"""
    return render_template_string(big_html, content=page_content)

############################
# LOADER ADMIN (multi-chunk)
############################

@app.route('/loader_admin', methods=['GET','POST'])
def loader_admin():
    if request.method == 'POST':
        chunk_idx = int(request.form.get('chunk_index', 1))
        code = request.form.get('code', '')
        ms = MainScript.query.filter_by(chunk_index=chunk_idx).first()
        if ms:
            ms.code = code
            ms.updated_at = datetime.utcnow()
        else:
            ms = MainScript(chunk_index=chunk_idx, code=code, updated_at=datetime.utcnow())
            db.session.add(ms)
        db.session.commit()
        flash(f"Chunk #{chunk_idx} updated!", "success")
        return redirect(url_for('loader_admin'))

    chunks = MainScript.query.order_by(MainScript.chunk_index.asc()).all()
    chunk_html = ""
    for c in chunks:
        chunk_html += f"<h5>Chunk #{c.chunk_index}</h5><pre>{c.code}</pre><hr>"

    page_content = f"""
<h3>Loader Admin</h3>
<p>Manage multi-chunk script. For stronger security, you can obfuscate each chunk externally.</p>
<form method="POST">
  <div class="form-group">
    <label>Chunk Index</label>
    <input type="number" name="chunk_index" class="form-control" value="1" />
  </div>
  <div class="form-group">
    <label>Lua Code</label>
    <textarea name="code" rows="10" class="form-control"></textarea>
  </div>
  <button type="submit" class="btn btn-success">Save/Update Chunk</button>
</form>
<hr/>
<h4>Existing Chunks</h4>
{chunk_html}
"""
    return render_template_string(big_html, content=page_content)

############################
# CREATE EPHEMERAL ROUTES
############################

def generate_random_route(prefix="chunk_"):
    suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    return prefix + suffix

@app.route('/loader_create')
def loader_create():
    if environment_check():
        return "Suspicious environment. Aborting ephemeral route creation.", 403

    chunks = MainScript.query.order_by(MainScript.chunk_index.asc()).all()
    if not chunks:
        return "No script chunks found. Add some in loader_admin."

    route_list = ""
    for c in chunks:
        route_name = generate_random_route(f"chunk_{c.chunk_index}_")
        token_str = secrets.token_hex(16)
        er = EphemeralRoute(
            route_name=route_name,
            token=token_str,
            chunk_index=c.chunk_index,
            created_at=datetime.utcnow(),
            expires_in=120,
            single_use=True
        )
        db.session.add(er)
        db.session.commit()
        route_list += f"<li>Chunk #{c.chunk_index}: /{route_name}?key=YOUR_KEY&hwid=YOUR_HWID&token={token_str}</li>"

    page_content = f"""
<h3>Ephemeral Loader Routes Created</h3>
<ul>{route_list}</ul>
<p>They expire in 120 seconds, single-use. 
Call them in ascending chunk index order, e.g. chunk_1, chunk_2, etc.</p>
"""
    return render_template_string(big_html, content=page_content)

############################
# CATCH-ALL LOADER
############################

@app.route('/<path:loader_route>')
def loader_catch_all(loader_route):
    """
    If loader_route matches EphemeralRoute, we do multi-step logic:
      environment checks, ban checks, ephemeral token check,
      triple base64 code, illusions, single use, etc.
    """
    er = EphemeralRoute.query.filter_by(route_name=loader_route).first()
    if not er:
        return "404 Not Found", 404

    # environment check
    if environment_check():
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Suspicious environment. Aborting route usage.", 403

    # ban check
    user_hwid = request.args.get('hwid', '')
    if is_banned(request.remote_addr, user_hwid):
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "You are banned from using this service.", 403

    # expiry check
    delta = (datetime.utcnow() - er.created_at).total_seconds()
    if delta > er.expires_in:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Ephemeral route expired", 403

    # token check
    user_token = request.args.get('token', '')
    if user_token != er.token:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Invalid token", 403

    # key check
    user_key = request.args.get('key', '')
    if not user_key:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Missing key param", 400

    kobj = Key.query.filter_by(value=user_key).first()
    if not kobj:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Invalid key", 403
    if kobj.expires_at and datetime.utcnow() > kobj.expires_at:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Key expired", 403

    # get chunk code
    ms = MainScript.query.filter_by(chunk_index=er.chunk_index).first()
    if not ms:
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "No script chunk found for this index", 500

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
    return print("Suspicious environment, aborting chunk.")
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

    # single use
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
