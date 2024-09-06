import shutil
from pathlib import Path


def setup_config():
    # Define the user's config directory
    user_config_dir = Path.home() / ".surf_controller"
    user_config_file = user_config_dir / "config.toml"

    # Create the directory if it doesn't exist
    user_config_dir.mkdir(parents=True, exist_ok=True)

    # If the user's config file doesn't exist, copy the default one
    if not user_config_file.exists():
        print("You are running surf_controller for the first time.")
        print("Surfcontroller will guide you through the setup process.")
        default_config = Path(__file__).parent / "config.toml"
        shutil.copy(default_config, user_config_file)


setup_config()

__version__ = "0.3.3"
print(
    f"Welcome to surf_controller version {__version__}"
)
