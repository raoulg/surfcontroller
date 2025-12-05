# 🏄‍♂️ Surf Controller

## 🌊 Overview

Surf Controller is a powerful CLI tool for managing your cloud workspaces with ease! It provides a user-friendly interface to monitor, pause, and resume your virtual machines (VMs) effortlessly.

## 🚀 Features

- 📊 Interactive CLI interface
- 🔄 Real-time VM status updates
- ⏸️ Pause and ▶️ resume VMs with a single keystroke
- 📋 Multi-select functionality for batch operations
- 📜 Live log viewing

## 🛠️ Installation

### config dir

By default, your `~/.surf_controller/` dir will be used for data.
You can modify this by specifying `SURF_CONTROLLER_CONFIG_DIR` in your env, eg
```bash
export SURF_CONTROLLER_CONFIG_DIR=/srv/shared/
```

You can do this for the server for all users with
```bash
sudo vim /etc/profile.d/shared_env.sh
```

### install as tool
Use [uv](https://docs.astral.sh/uv/concepts/tools/) to install surf-controller globally or add it to your local environment. You can install it with `curl -LsSf https://astral.sh/uv/install.sh | sh` . Of course, you can also use pip to install it (but then you might also need to install python etc, something uv also takes care of).
Here are three different commands you could use, the first one (uv tools) is recommended to install it globally.
Dont run all three, pick one.

#### option 1
install globally

```
uv tools install surf-controller
```

#### option 2
install in a .venv
```
uv add surf-controller
```


#### option 3
Install with pip if you get nervous from new tools
```
pip install surf-controller
```

All three commands install the `surfcontroller` command; if you dont know what to pick, use `uv`


## 🔑 First-time Setup of tokens

You can find the SURF API documentation here: [API Documentation](https://servicedesk.surf.nl/wiki/display/WIKI/SRC+API)

On your [profile](https://portal.live.surfresearchcloud.nl/profile) you can create your own API token.

You can obtain the CSRF tokens by authorizing directly with the [Surf API](https://gw.live.surfresearchcloud.nl/v1/workspace/swagger/docs/).
Use the green lock icon in the top right corner to authorize with your API-token and obtain the CSRF token by executing a request.

Copy both tokens and use them during configuration.

Run the configuration by starting the controller:
```
surfcontroller
```

On first run, Surf Controller will:

1. 📁 Create a configuration directory in your SURF_CONTROLLER_CONFIG_DIR folder (defaults to ~)
2. 📄 Copy a default configuration file into your configdir
3. 🔒 Prompt you for API and CSRF tokens and stores them in your configdir

## 🎮 Usage

Run the controller:
```
surfcontroller
```

### 🕹️ Controls

#### navigate / select
- `j`: Move cursor down
- `k`: Move cursor up
- `J`: Next page
- `K`: Previous page
- `Enter`: Select/deselect VM
- `a`: toggle Select all VMs
- `f`: toggle Filter VMs (by username)
- `R`: toggle Filter Running VMs (show only running)
- `1-9`: Toggle custom filters
- `+`: Add custom filter
- `n`: rename username
- `l`: toggle view logs

#### Actions
- `p`: Pause selected VMs
- `r`: Resume selected VMs
- `e`: Batch update End Date for selected VMs
- `E`: Toggle Pause Exclusion (Shift+e)
- `c`: Bulk Create VMs (Wizard)
- `d`: Bulk Delete selected VMs (with confirmation)
- `u`: Update VM list
- `s`: ssh into selected VM (select just one VM)

### ✨ New in v1.0
- **Bulk Creation Wizard**: Press `c` to launch a step-by-step wizard for creating multiple VMs from a user list and template.
- **Bulk Deletion**: Press `d` to delete multiple VMs at once. Includes a safety confirmation dialog.
- **Batch End Date Update**: Press `e` to update the expiration date for multiple VMs simultaneously.
- **Running Filter**: Press `R` to quickly see only your running VMs.
- **UI Improvements**:
    - **Progress Bars**: Visual progress tracking for batch operations.
    - **Status Indicators**: Clear "OK" (Green) or "FAILED" (Red) status for actions.
    - **Responsive Footer**: Command bar adapts to screen width.
    - **Persistent Filters**: Custom filters are saved between sessions.

Note that adding to the exclusion list only adds the id of the vm to `exclusions.json`. The actual shutting down of the VM is done from a VM we control on the Surf cloud, so toggling this on your computer doesnt impact the actual pausing at 21:00.

## 📝 Configuration

Edit `~/.surf_controller/config.toml` to customize your settings.

## 🤝 Contributing
Contributions are welcome!

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Thanks to https://claude.ai/ for help with the curses implementation

## 📅 Scheduler & Web GUI

The project includes a Docker-based scheduler for automating nightly VM pauses and managing exclusions via a Web GUI.

### Setup

1.  Navigate to the `scheduler/` directory:
    ```bash
    cd scheduler
    ```
2.  Create a `.env` file from the sample:
    ```bash
    cp .env.sample .env
    ```
    Edit `.env` to set your desired `WEB_USERNAME` and `WEB_PASSWORD`.
3.  Start the scheduler:
    ```bash
    docker-compose up -d --build
    ```

### How it works

- **Web GUI**: Accessible at `http://localhost:5001`. Use it to view VM status, toggle exclusions, and manually trigger the pause job.
- **Nightly Job**: A cron job runs every night at 21:00 to pause all non-excluded VMs.
- **Configuration**: The scheduler mounts your local `~/.surf_controller` directory, so it shares the same tokens and exclusions as the CLI tool.
- **Installation**: The Docker image installs the `surf-controller` package directly from the source code in the parent directory, ensuring it always runs the latest version of your code.

### 🚀 Deployment

To deploy the scheduler to a remote machine:

- Copy `scheduler/docker-compose.deploy.yml` to the remote server (e.g., as `docker-compose.yml`).
- Ensure the config directory exists (e.g., `/srv/shared/.surf_controller`) and contains your tokens.
- Run:
    ```bash
    docker-compose up -d
    ```

