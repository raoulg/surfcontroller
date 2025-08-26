from pathlib import Path
import os

BASE_DIR = Path(os.getenv("SURF_CONTROLLER_CONFIG_DIR", Path.home()))
USER_CONFIG_DIR = BASE_DIR / ".surf_controller"
USER_CONFIG_FILE = USER_CONFIG_DIR / "config.toml"
LOG_FILE = USER_CONFIG_DIR / "logs.log"
