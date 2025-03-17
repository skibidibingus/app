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
    <!-- Exec Chart -->
    <div class="chart-container p-3 mb-4">
      <h5>Executions Over Time</h5>
      <canvas id="execChart"></canvas>
    </div>
    <!-- Revenue Chart -->
    <div class="chart-container p-3 mb-4">
      <h5>Revenue Over Time</h5>
      <canvas id="revenueChart"></canvas>
    </div>
    <!-- Projects Table -->
    <div class="card mb-4">
      <div class="card-body">
        <h5 class="card-title">Projects</h5>
        <table class="table table-dark table-striped">
          <thead>
            <tr><th>Name</th><th>Created</th><th>Actions</th></tr>
          </thead>
          <tbody>
    """

    for p in projects:
        dashboard_content += f"""
            <tr>
              <td>{p.name}</td>
              <td>{p.created_at.strftime('%Y-%m-%d')}</td>
              <td>
                <a href="/scripts/{p.id}" class="btn btn-sm btn-info">View Scripts</a>
                <a href="#" class="btn btn-sm btn-purple">Edit</a>
                <a href="#" class="btn btn-sm btn-danger">Delete</a>
              </td>
            </tr>
        """

    dashboard_content += """
          </tbody>
        </table>
        <button class="btn btn-success btn-sm">+ Create Project</button>
      </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
      const execData = """ + str(exec_chart_data) + """;
      const revData = """ + str(revenue_chart_data) + """;
      
      // Create execution chart
      const execCtx = document.getElementById('execChart').getContext('2d');
      new Chart(execCtx, {
        type: 'line',
        data: {
          labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug'],
          datasets: [{
            label: 'Executions',
            data: execData,
            borderColor: '#4e73df',
            backgroundColor: 'rgba(78, 115, 223, 0.05)',
            borderWidth: 3,
            pointBackgroundColor: '#4e73df',
            pointBorderColor: '#fff',
            pointRadius: 3,
            pointHoverRadius: 5,
            tension: 0.3,
            fill: true
          }]
        },
        options: {
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: false
            }
          },
          scales: {
            y: {
              grid: {
                color: 'rgba(255, 255, 255, 0.1)'
              },
              ticks: {
                color: '#aaa'
              }
            },
            x: {
              grid: {
                display: false
              },
              ticks: {
                color: '#aaa'
              }
            }
          }
        }
      });
      
      // Create revenue chart
      const revCtx = document.getElementById('revenueChart').getContext('2d');
      new Chart(revCtx, {
        type: 'bar',
        data: {
          labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug'],
          datasets: [{
            label: 'Revenue ($)',
            data: revData,
            backgroundColor: '#1cc88a',
            borderRadius: 3,
            maxBarThickness: 30
          }]
        },
        options: {
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: false
            }
          },
          scales: {
            y: {
              grid: {
                color: 'rgba(255, 255, 255, 0.1)'
              },
              ticks: {
                color: '#aaa'
              }
            },
            x: {
              grid: {
                display: false
              },
              ticks: {
                color: '#aaa'
              }
            }
          }
        }
      });
    </script>
    """

    return render_template_string(
        big_html,
        page='dashboard',
        dashboard_content=dashboard_content,
        kill_switch_active=kill_switch_active
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

############################
# MAIN
############################

# Create tables and seed data on application startup
with app.app_context():
    db.create_all()
    seed_data()
################################## start
if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5000)
<li onclick="window.location.href='/loader_admin'">
  <i class="bi bi-file-earmark-lock"></i>
  <span>Loader</span>
</li>
############################################################
# LOADER ADMIN PAGE (like "LuaArmor" style)
############################################################
@app.route('/loader_admin', methods=['GET','POST'])
def loader_admin():
    """
    Manage the main script in multiple chunks (like chunk_index=1,2,...).
    For real Luarmor-level protection, you'd run each chunk 
    through a robust Lua obfuscator externally.
    """
    # Let's assume you have a MainScript model with fields:
    #   chunk_index (int)
    #   code (text)
    #   updated_at (datetime)
    # You can store as many chunks as you want.

    if request.method == 'POST':
        # If user is adding/updating a chunk
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
        flash(f"Chunk #{chunk_idx} updated or created!", "success")
        return redirect(url_for('loader_admin'))

    # Display existing chunks
    chunks = MainScript.query.order_by(MainScript.chunk_index.asc()).all()
    chunk_list_html = ""
    for c in chunks:
        chunk_list_html += f"<h5>Chunk #{c.chunk_index}</h5><pre>{c.code}</pre><hr>"

    page_html = f"""
<h3>Loader Admin</h3>
<p>This page manages the script in multiple chunks. 
For strong security, also obfuscate each chunk externally.</p>

<form method="POST">
  <div class="form-group">
    <label>Chunk Index</label>
    <input type="number" name="chunk_index" class="form-control" value="1" />
  </div>
  <div class="form-group">
    <label>Lua Code (obfuscated if possible)</label>
    <textarea name="code" rows="10" class="form-control"></textarea>
  </div>
  <button type="submit" class="btn btn-success btn-sm">Save Chunk</button>
</form>
<hr/>
<h4>Current Chunks</h4>
{chunk_list_html}
"""
    return render_template_string(big_html, page='loader_admin', dashboard_content=page_html)


############################################################
# CREATE EPHEMERAL ROUTES FOR THE LOADER (multi-step approach)
############################################################
@app.route('/loader_create')
def loader_create():
    """
    This route dynamically creates ephemeral routes for each chunk 
    in the MainScript. Each route is short-lived, single-use, 
    and requires a token, plus ?key=... & ?hwid=... in the query.
    The user calls them in ascending chunk_index order.
    """
    # environment check
    if environment_check():
        return "Suspicious environment. Aborting ephemeral route creation.", 403

    # Suppose your MainScript has multiple chunks
    chunks = MainScript.query.order_by(MainScript.chunk_index.asc()).all()
    if not chunks:
        return "No script chunks found. Add some in /loader_admin."

    route_infos = []
    for c in chunks:
        route_name = generate_random_route(f"chunk_{c.chunk_index}_")
        token_str = secrets.token_hex(16)
        # ephemeral route DB row
        er = EphemeralRoute(
            route_name=route_name,
            token=token_str,
            stage=1,               # or stage=c.chunk_index, if you prefer
            chunk_index=c.chunk_index,
            created_at=datetime.utcnow(),
            expires_in=120,
            single_use=True
        )
        db.session.add(er)
        db.session.commit()
        route_infos.append((c.chunk_index, route_name, token_str))

    # Show them to the admin
    route_list = ""
    for idx, rname, tkn in route_infos:
        route_list += f"<li>Chunk #{idx}: /{rname}?key=YOUR_KEY&hwid=YOUR_HWID&token={tkn}</li>"

    page_html = f"""
<h3>Ephemeral Loader Routes Created</h3>
<ul>
{route_list}
</ul>
<p>They expire in 120 seconds, single-use. The user must call them in ascending chunk index order.
If you want to embed chunk2 route inside chunk1, you'll do that in the chunk code itself.</p>
"""
    return render_template_string(big_html, page='loader_create', dashboard_content=page_html)


############################################################
# CATCH-ALL FOR LOADER ROUTES
############################################################
@app.route('/<path:loader_route>')
def loader_catch_all(loader_route):
    """
    If loader_route matches an EphemeralRoute, we do the multi-step logic:
      - environment checks
      - ban checks
      - ephemeral token checks
      - fetch the chunk code from MainScript
      - triple base64 or any advanced measure
      - illusions / partial server logic
      - single-use route if desired
    """
    er = EphemeralRoute.query.filter_by(route_name=loader_route).first()
    if not er:
        return "404 Not Found", 404

    # environment check
    if environment_check():
        # log usage as suspicious
        log_usage(er.route_name, request.remote_addr, suspicious=True)
        return "Suspicious environment. Aborting loader route usage.", 403

    # check ban
    user_hwid = request.args.get('hwid', '')
    if is_banned(request.remote_addr, user_hwid):
        log_usage(er.route_name, request.remote_addr, user_hwid, suspicious=True)
        return "You are banned from using this service.", 403

    # check expiry
    delta = (datetime.utcnow() - er.created_at).total_seconds()
    if delta > er.expires_in:
        log_usage(er.route_name, request.remote_addr, user_hwid, suspicious=True)
        return "Ephemeral route expired", 403

    # check token
    user_token = request.args.get('token', '')
    if user_token != er.token:
        log_usage(er.route_name, request.remote_addr, user_hwid, suspicious=True)
        return "Invalid token for ephemeral route", 403

    # check key param
    user_key = request.args.get('key', '')
    if not user_key:
        log_usage(er.route_name, request.remote_addr, user_hwid, suspicious=True)
        return "Missing key param", 400

    # validate key
    kobj = Key.query.filter_by(value=user_key).first()
    if not kobj:
        log_usage(er.route_name, request.remote_addr, user_hwid, suspicious=True)
        return "Invalid key", 403
    if kobj.expires_at and datetime.utcnow() > kobj.expires_at:
        log_usage(er.route_name, request.remote_addr, user_hwid, suspicious=True)
        return "Key expired", 403

    # get the chunk from MainScript
    chunk_idx = er.chunk_index
    ms = MainScript.query.filter_by(chunk_index=chunk_idx).first()
    if not ms:
        log_usage(er.route_name, request.remote_addr, user_hwid, suspicious=True)
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

    # log usage normal
    log_usage(er.route_name, request.remote_addr, user_hwid, suspicious=False)
    return Response(final_lua, mimetype='text/plain')
