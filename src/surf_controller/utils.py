import logging
import sys
import tomllib
from surf_controller.setup import USER_CONFIG_FILE, LOG_FILE


def get_config(configfile=USER_CONFIG_FILE):
    with open(configfile, "rb") as f:
        return tomllib.load(f)


def setup_logger(log_file=LOG_FILE, use_curses=True):
    """
    Sets up a logger that prints useful information such as filename, line number, and time.
    The logger will save logs to a specified log file, and optionally output to console if not in curses mode.

    :param log_file: The name of the log file where logs should be saved (default is '.surf_controller/logs.log' in user's home directory)
    :param use_curses: Boolean flag to indicate if the script is running in curses mode
    :return: Configured logger instance
    """
    # Create a custom logger
    logger = logging.getLogger(__name__)

    # Set the minimum logging level
    logger.setLevel(logging.INFO)

    # Ensure the directory for the log file exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create and set up the file handler
    f_handler = logging.FileHandler(log_file)
    f_handler.setLevel(logging.INFO)
    f_formatter = logging.Formatter(
        "%(asctime)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s"
    )
    f_handler.setFormatter(f_formatter)
    logger.addHandler(f_handler)

    if not use_curses:
        # Only add console handler if not in curses mode
        c_handler = logging.StreamHandler(sys.stdout)
        c_handler.setLevel(logging.INFO)

        # Define ANSI color codes
        RESET = "\033[0m"
        COLOR_MAP = {
            logging.DEBUG: "\033[34m",  # Blue
            logging.INFO: "\033[32m",  # Green
            logging.WARNING: "\033[33m",  # Yellow
            logging.ERROR: "\033[31m",  # Red
            logging.CRITICAL: "\033[41m",  # Red background
        }

        class CustomFormatter(logging.Formatter):
            def format(self, record):
                record.asctime = self.formatTime(record, self.datefmt)
                log_color = COLOR_MAP.get(record.levelno, RESET)
                log_msg = f"{log_color}{record.asctime} - {record.filename} - {record.lineno} - {record.levelname} - {RESET}{record.msg}"
                return log_msg

        c_formatter = CustomFormatter(
            "%(asctime)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s"
        )
        c_handler.setFormatter(c_formatter)
        logger.addHandler(c_handler)

    return logger


config = get_config()
logger = setup_logger()
