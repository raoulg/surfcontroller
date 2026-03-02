import os
import subprocess
from functools import wraps
from pathlib import Path
from datetime import datetime, timedelta
import json

from flask import Flask, Response, redirect, render_template, request, url_for
import pandas as pd
import plotly.express as px
import plotly.utils

from surf_controller.api import Workspace
from surf_controller.setup import USER_CONFIG_DIR, LOG_FILE

app = Flask(__name__)

# Configuration
USERNAME = os.environ.get("WEB_USERNAME", "admin")
PASSWORD = os.environ.get("WEB_PASSWORD", "password")


def check_auth(username, password):
    return username == USERNAME and password == PASSWORD


def authenticate():
    return Response(
        "Could not verify your access level for that URL.\n"
        "You have to login with proper credentials",
        401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'},
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)

    return decorated


@app.route("/")
@requires_auth
def index():
    workspace = Workspace()
    # Force reload to get latest status
    vms = workspace.get_workspaces(save=False)
    exclusions = workspace.load_exclusions()

    # Sort VMs: Excluded first, then Running, then by name
    vms.sort(
        key=lambda x: (0 if x.id in exclusions else 1, 0 if x.active else 1, x.name)
    )

    # Read last run status
    last_run = "Never"
    try:
        log_file = USER_CONFIG_DIR / "last_run.txt"
        if log_file.exists():
            last_run = log_file.read_text().strip()
    except Exception:
        pass

    return render_template(
        "index.html", vms=vms, exclusions=exclusions, last_run=last_run
    )


@app.route("/dashboard")
@requires_auth
def dashboard():
    shutdown_file = USER_CONFIG_DIR / "shutdowns.csv"
    time_filter = request.args.get("filter", "all")
    
    if not shutdown_file.exists():
        return render_template("dashboard.html", plot_json=None, top_users=None, filter=time_filter)

    df = pd.read_csv(shutdown_file)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Apply filter
    now = datetime.now()
    if time_filter == "week":
        df = df[df["timestamp"] > (now - timedelta(weeks=1))]
    elif time_filter == "month":
        df = df[df["timestamp"] > (now - timedelta(days=30))]

    if df.empty:
        return render_template("dashboard.html", plot_json=None, top_users=None, filter=time_filter)

    # Top 5 most frequently shut down VMs
    top_vms = df["vm_name"].value_counts().head(5).reset_index()
    top_vms.columns = ["VM Name", "Shutdown Count"]

    fig = px.bar(top_vms, x="VM Name", y="Shutdown Count", title="Top 5 Most Shut Down VMs")
    plot_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    # Calculate usage hours for top VMs (this part is slow if many VMs, so only for top ones)
    top_vm_ids = df["vm_id"].value_counts().head(10).index.tolist()
    workspace_api = Workspace()
    
    vm_usage_data = [] # List of dicts for each VM
    
    for vm_id in top_vm_ids:
        details = workspace_api.get_workspace_details(vm_id)
        if not details:
            continue
            
        vm_name = details.get("name", "Unknown")
        actions = details.get("workspace_actions", [])
        
        # Sort actions by time, earliest first for duration calculation
        actions.sort(key=lambda x: x["time_created"])
        
        total_seconds = 0
        last_resume = None
        
        for action in actions:
            if action["type"] == "resume" and action["status"] == "success":
                resumed_at_str = action.get("result", {}).get("resumed_at") or action["time_updated"]
                try:
                    last_resume = pd.to_datetime(resumed_at_str)
                except:
                    continue
            elif action["type"] == "pause" and action["status"] == "success" and last_resume:
                paused_at_str = action.get("result", {}).get("paused_at") or action["time_updated"]
                try:
                    paused_at = pd.to_datetime(paused_at_str)
                    total_seconds += (paused_at - last_resume).total_seconds()
                    last_resume = None
                except:
                    continue
        
        # If currently running, add time since last resume
        if details.get("active") and last_resume is not None:
            if last_resume.tzinfo is None:
                last_resume = last_resume.tz_localize('UTC')
            total_seconds += (pd.Timestamp.now(tz='UTC') - last_resume.tz_convert('UTC')).total_seconds()
            
        vm_usage_data.append({
            "vm_name": vm_name,
            "hours": round(total_seconds / 3600, 1),
            "shutdowns": df[df["vm_id"] == vm_id].shape[0]
        })

    vm_usage_data.sort(key=lambda x: x["hours"], reverse=True)

    return render_template("dashboard.html", plot_json=plot_json, top_vms_usage=vm_usage_data, filter=time_filter)


@app.route("/trigger-pause", methods=["POST"])
@requires_auth
def trigger_pause():
    # Run the pause job and redirect output to the same log file as cron
    try:
        with open("/var/log/cron.log", "a") as log_file:
            subprocess.Popen(
                ["/usr/local/bin/python", "pause_job.py"],
                stdout=log_file,
                stderr=log_file
            )
    except Exception as e:
        print(f"Error triggering job: {e}")

    return redirect(url_for("index"))


@app.route("/toggle/<vm_id>", methods=["POST"])
@requires_auth
def toggle_exclusion(vm_id):
    workspace = Workspace()
    exclusions = workspace.load_exclusions()

    if vm_id in exclusions:
        exclusions.remove(vm_id)
    else:
        exclusions.add(vm_id)

    workspace.save_exclusions(exclusions)
    return redirect(url_for("index"))


@app.route("/logs")
@requires_auth
def logs():
    log_content = ""
    
    # 1. Read App Logs (from the surf_controller logger)
    try:
        if LOG_FILE.exists():
            log_content += f"--- APPLICATION LOGS ({LOG_FILE}) ---\n"
            lines = LOG_FILE.read_text().splitlines()
            log_content += "\n".join(lines[-200:]) + "\n\n"
        else:
            log_content += f"Application log file not found at {LOG_FILE}\n\n"
    except Exception as e:
        log_content += f"Error reading application logs: {e}\n\n"

    # 2. Read Cron Logs
    try:
        log_path = Path("/var/log/cron.log")
        if log_path.exists():
            log_content += "--- CRON SYSTEM LOGS (/var/log/cron.log) ---\n"
            lines = log_path.read_text().splitlines()
            log_content += "\n".join(lines[-200:])
        else:
            log_content += "Cron log file not found at /var/log/cron.log\n"
    except Exception as e:
        log_content += f"Error reading cron logs: {e}"

    return render_template("logs.html", log_content=log_content)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
