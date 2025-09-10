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

```
uv tools install surf-controller
```

```
uv add surf-controller
```

```
pip install surf-controller
```

These commands all installs the `surfcontroller` command.


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
- `Enter`: Select/deselect VM
- `a`: toggle Select all VMs
- 'f': toggle Filter VMs (by username)
- 'n': rename username
- 'l': toggle view logs

#### Actions
- `p`: Pause selected VMs
- `r`: Resume selected VMs
- `e`: add VM to exclusion list
- 'u': Update VM list
- 's': ssh into selected VM (select just one VM)

Note that adding to the exclusion list only adds the id of the vm to `exclusions.json`. The actual shutting down of the VM is done from a VM we control on the Surf cloud, so toggling this on your computer doesnt impact the actual pausing at 21:00.

## 📝 Configuration

Edit `~/.surf_controller/config.toml` to customize your settings.

## 🤝 Contributing
Contributions are welcome!

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Thanks to https://claude.ai/ for help with the curses implementation
