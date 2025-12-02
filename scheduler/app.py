import os
from functools import wraps
from flask import Flask, render_template, request, Response, redirect, url_for
from surf_controller.api import Workspace

app = Flask(__name__)

# Configuration
USERNAME = os.environ.get("WEB_USERNAME", "admin")
PASSWORD = os.environ.get("WEB_PASSWORD", "password")

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def authenticate():
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

from pathlib import Path
import subprocess

@app.route('/')
@requires_auth
def index():
    workspace = Workspace()
    # Force reload to get latest status
    vms = workspace.get_workspaces(save=False)
    exclusions = workspace.load_exclusions()
    
    # Sort VMs: Excluded first, then Running, then by name
    vms.sort(key=lambda x: (0 if x.id in exclusions else 1, 0 if x.active else 1, x.name))
    
    # Read last run status
    last_run = "Never"
    try:
        log_file = Path("/config/last_run.txt")
        if log_file.exists():
            last_run = log_file.read_text().strip()
    except Exception:
        pass
    
    return render_template('index.html', vms=vms, exclusions=exclusions, last_run=last_run)

@app.route('/trigger-pause', methods=['POST'])
@requires_auth
def trigger_pause():
    # Run the pause job in the background (or foreground for simplicity here)
    try:
        subprocess.Popen(["python", "pause_job.py"])
    except Exception as e:
        print(f"Error triggering job: {e}")
        
    return redirect(url_for('index'))

@app.route('/toggle/<vm_id>', methods=['POST'])
@requires_auth
def toggle_exclusion(vm_id):
    workspace = Workspace()
    exclusions = workspace.load_exclusions()
    
    if vm_id in exclusions:
        exclusions.remove(vm_id)
    else:
        exclusions.add(vm_id)
        
    workspace.save_exclusions(exclusions)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
