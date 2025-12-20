import shutil
from pathlib import Path

from surf_controller.setup import USER_CONFIG_DIR, USER_CONFIG_FILE


def setup_config():
    # Create the directory if it doesn't exist
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # If the user's config file doesn't exist, copy the default one
    if not USER_CONFIG_FILE.exists():
        print("You are running surf_controller for the first time.")
        print("Surfcontroller will guide you through the setup process.")
        default_config = Path(__file__).parent / "config.toml"
        shutil.copy(default_config, USER_CONFIG_FILE)


setup_config()

__version__ = "1.1.3"
print(f"Welcome to surf_controller version {__version__}")
