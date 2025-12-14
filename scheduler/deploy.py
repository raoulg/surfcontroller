#!/usr/bin/env python3
import os
import subprocess
import secrets
import sys
from pathlib import Path

# Configuration
SCHEDULER_DIR = Path(__file__).parent.absolute()
ENV_FILE = SCHEDULER_DIR / ".env"
ENV_SAMPLE = SCHEDULER_DIR / ".env.sample"
DOCKER_FILE = SCHEDULER_DIR / "Dockerfile"
COMPOSE_DEPLOY = SCHEDULER_DIR / "docker-compose.deploy.yml"
IMAGE_NAME = "raoulgrouls/surf-scheduler:latest"
DEFAULT_HOST_IP = "123.44.67.89"
DEFAULT_USER = "yourusername"
REMOTE_PATH = "/srv/shared/mads_demoserver"

def load_env(env_path):
    config = {}
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    try:
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()
                    except ValueError:
                        pass
    return config

def save_env(env_path, config):
    with open(env_path, "w") as f:
        for key, value in config.items():
            f.write(f"{key}={value}\n")

def check_env():
    """Ensures .env exists with WEB_PASSWORD and DEPLOY_HOST."""
    config = load_env(ENV_FILE)
    dirty = False

    # Load defaults from sample if new
    if not ENV_FILE.exists() and ENV_SAMPLE.exists():
        print(f"[*] Initializing .env from {ENV_SAMPLE.name}...")
        sample_config = load_env(ENV_SAMPLE)
        config.update(sample_config)
        dirty = True

    # Check WEB_PASSWORD
    if "WEB_PASSWORD" not in config or config["WEB_PASSWORD"] in ["secret", ""]:
        print("[*] Generating secure WEB_PASSWORD...")
        config["WEB_PASSWORD"] = secrets.token_urlsafe(16)
        dirty = True

    # Check DEPLOY_HOST
    # Check REMOTE_USER
    if "REMOTE_USER" not in config:
        print(f"[*] REMOTE_USER not found.")
        user_input = input(f"Enter remote user [{DEFAULT_USER}]: ").strip()
        config["REMOTE_USER"] = user_input if user_input else DEFAULT_USER
        dirty = True

    # Check DEPLOY_HOST
    if "DEPLOY_HOST" not in config:
        print(f"[*] DEPLOY_HOST not found.")
        host_input = input(f"Enter deployment host IP [{DEFAULT_HOST_IP}]: ").strip()
        config["DEPLOY_HOST"] = host_input if host_input else DEFAULT_HOST_IP
        dirty = True
    
    if dirty:
        save_env(ENV_FILE, config)
        print(f"[*] Updated {ENV_FILE}")
        
    return config

def run_command(cmd, cwd=None, shell=False):
    """Runs a shell command and raises error on failure."""
    print(f"[$] {cmd}")
    try:
        # If shell=True, cmd should be a string. If shell=False, list.
        # Here we use shell=True for complex commands or simple list for others.
        # Standardizing on string for display and list for execution where possible,
        # but for simplicity/piping rely on shell=True occasionally or splitting.
        
        if isinstance(cmd, list):
            cmd_str = " ".join(cmd)
        else:
            cmd_str = cmd
            shell = True
            
        subprocess.check_call(cmd if not shell else cmd_str, cwd=cwd, shell=shell)
    except subprocess.CalledProcessError as e:
        print(f"[!] Command failed: {e}")
        sys.exit(1)

def main():
    print("--- Surf Scheduler Deployment ---")
    
    # 1. Environment Setup
    config = check_env()
    deploy_host = config["DEPLOY_HOST"]
    deploy_user = config["REMOTE_USER"]
    remote_target = f"{deploy_user}@{deploy_host}"
    
    print(f"[*] Target: {remote_target}")
    print(f"[*] Web Password: {config['WEB_PASSWORD'][:5]}...")

    # 2. Docker Build & Push
    print("\n--- Building and Pushing Docker Image ---")
    # Using string for complex command with flags
    # We must run from project root because Dockerfile COPY commands expect 'scheduler/' prefix
    # and we need pyproject.toml from root for 'uv build'
    project_root = SCHEDULER_DIR.parent
    build_cmd = f"docker buildx build --platform linux/amd64 -t {IMAGE_NAME} -f scheduler/Dockerfile . --push"
    run_command(build_cmd, cwd=project_root, shell=True)

    # 3. Deploy Files
    print("\n--- Deploying Configuration Files ---")
    
    # Copy docker-compose.deploy.yml -> surfcontroller.yml
    scp_cmd_1 = f"scp {COMPOSE_DEPLOY} {remote_target}:{REMOTE_PATH}/surfcontroller.yml"
    run_command(scp_cmd_1, shell=True)
    
    # Copy .env
    scp_cmd_2 = f"scp {ENV_FILE} {remote_target}:{REMOTE_PATH}/.env"
    run_command(scp_cmd_2, shell=True)

    # 4. Remote Execution
    print("\n--- Restarting Remote Service ---")
    
    remote_cmds = [
        f"cd {REMOTE_PATH}",
        "docker compose -f surfcontroller.yml pull",
        "docker compose -f surfcontroller.yml down",
        "docker compose -f surfcontroller.yml up -d",
        "docker compose -f surfcontroller.yml ps"
    ]
    
    # Join commands with && for safety
    remote_cmd_str = " && ".join(remote_cmds)
    ssh_cmd = f"ssh {remote_target} '{remote_cmd_str}'"
    
    run_command(ssh_cmd, shell=True)

    print("\n[+] Deployment Complete!")

if __name__ == "__main__":
    main()
