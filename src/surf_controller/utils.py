import logging
import tomllib
from pathlib import Path


def get_config(configfile=Path.home() / ".surf_controller/config.toml"):
    with open(configfile, "rb") as f:
        return tomllib.load(f)


def setup_logger(log_file=Path.home() / ".surf_controller/logs.log"):
    """
    Sets up a logger that prints useful information such as filename, line number, and time.
    The logger will also save logs to a specified log file, with colored output to the console.

    :param log_file: The name of the log file where logs should be saved (default is 'logs.log')
    :return: Configured logger instance
    """
    # Create a custom logger
    logger = logging.getLogger(__name__)

    # Set the minimum logging level (could be DEBUG, INFO, WARNING, ERROR, CRITICAL)
    logger.setLevel(logging.INFO)

    # Create handlers
    c_handler = logging.StreamHandler()  # Console handler
    f_handler = logging.FileHandler(log_file)  # File handler

    # Set level for handlers
    c_handler.setLevel(logging.INFO)
    f_handler.setLevel(logging.INFO)

    # Define ANSI color codes
    RESET = "\033[0m"
    COLOR_MAP = {
        logging.DEBUG: "\033[34m",  # Blue
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[41m",  # Red background
    }

    # Custom formatter that includes colors
    class CustomFormatter(logging.Formatter):
        def format(self, record):
            # Use the original format time method to get the asctime
            record.asctime = self.formatTime(record, self.datefmt)
            log_color = COLOR_MAP.get(record.levelno, RESET)
            log_msg = f"{log_color}{record.asctime} - {record.filename} - {record.lineno} - {record.levelname} - {RESET}{record.msg}"
            return log_msg

    formatter = CustomFormatter(
        "%(asctime)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s"
    )

    # Set the formatter for both console and file handlers
    c_handler.setFormatter(formatter)
    f_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s"
        )
    )

    # Add handlers to the logger
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)

    return logger


config = get_config()
logger = setup_logger()
