import argparse
import csv
import curses
import json
import shutil
import time
from collections import namedtuple
from pathlib import Path

import requests

from surf_controller.utils import config, logger


class Action:
    def __init__(self):
        self.scriptdir = Path.home() / config["files"]["scriptdir"]
        self.URL = config["surf"]["URL"]
        self.auth_token_file = self.scriptdir / config["files"]["api-token"]
        if self.auth_token_file.exists():
            self.AUTH_TOKEN = self.auth_token_file.read_text().strip()
        else:
            logger.warning(f"API token not found at {self.auth_token_file}")
        self.csrf_token_file = self.scriptdir / config["files"]["csrf-token"]
        if self.csrf_token_file.exists():
            self.CSRF_TOKEN = self.csrf_token_file.read_text().strip()
        else:
            logger.warning(f"CSRF token not found at {self.csrf_token_file}")
        self.OUTPUT_FILE = self.scriptdir / config["files"]["ids"]

    def __call__(self, do: str, data: list, id_filter: list):
        for item in data:
            timestamp = time.strftime("%d-%m-%Y %H:%M:%S")
            if id_filter and item.name not in id_filter:
                logger.debug(
                    f"{timestamp} | {item.name} | {item.id} | active: {item.active} : skipping (not in id_filter)"
                )
                continue

            logger.info(
                f"{timestamp} | {item.name} | {item.id} | active: {item.active} : Attempt to {do}..."
            )

            full_url = f"{self.URL}/{item.id}/actions/{do}/"
            headers = {
                "accept": "application/json;Compute",
                "authorization": self.AUTH_TOKEN,
                "Content-Type": f"application/json;{do}",
                "X-CSRFTOKEN": self.CSRF_TOKEN,
            }

            response = requests.post(full_url, headers=headers, data="{}")

            if response.status_code == 400:
                logger.warning(
                    f"{timestamp} | {item.name} | {item.id} | active:{item.active} : Error {do}"
                )
                logger.warning(
                    f"{timestamp} | {item.name} | {item.id} | active:{item.active} : {response.text}"
                )
            else:
                logger.info(
                    f"{timestamp} | {item.name} | {item.id} | active:{item.active} : Success {do}"
                )
        logger.info(f"Finished {do} for all workspaces")


class Workspace:
    def __init__(self):
        self.scriptdir = Path.home() / config["files"]["scriptdir"]
        self.URL = config["surf"]["URL"] + "/?application_type=Compute&deleted=false"
        self.auth_token_file = self.scriptdir / config["files"]["api-token"]
        if self.auth_token_file.exists():
            self.AUTH_TOKEN = self.auth_token_file.read_text().strip()
        else:
            logger.warning(f"API token not found at {self.auth_token_file}")
        self.OUTPUT_FILE = self.scriptdir / config["files"]["ids"]

        # Set up the headers for the request
        self.headers = {
            "accept": "application/json;Compute",
            "authorization": self.AUTH_TOKEN,
        }

    def get_workspaces(self, save=False):
        # Make the GET request
        response = requests.get(self.URL, headers=self.headers)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()
            if save:
                self.save(data)

            results = []
            Data = namedtuple("Data", ["id", "name", "active"])
            for result in data["results"]:
                results.append(Data(result["id"], result["name"], result["active"]))
            return results
        else:
            logger.info(f"Failed to fetch data. Status code: {response.status_code}")
            return None

    def save(self, data: dict):
        with self.OUTPUT_FILE.open("w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["id", "name", "active"])  # Write header
            for result in data["results"]:
                writer.writerow([result["id"], result["name"], result["active"]])

        logger.info(f"Data successfully saved to {self.OUTPUT_FILE}")


def first_run(stdscr: curses.window):
    scriptdir = Path.home() / config["files"]["scriptdir"]
    if not scriptdir.exists():
        logger.info(f"Creating directory {scriptdir}")
        scriptdir.mkdir(parents=True)

    user_config_file = scriptdir / "config.toml"
    if not user_config_file.exists():
        default_config = Path(__file__).parent / "config.toml"
        shutil.copy(default_config, user_config_file)
        logger.info(f"Created default configuration file at {user_config_file}")

    auth_token_file = scriptdir / config["files"]["api-token"]
    auth_created = False
    csrf_token_file = scriptdir / config["files"]["csrf-token"]
    csrf_created = False

    def get_user_input(prompt):
        curses.echo()
        stdscr.clear()
        stdscr.addstr(1, 0, "Press 'Enter' to submit")
        stdscr.addstr(2, 0, "Press 'ctrl-C' to cancel")
        stdscr.addstr(0, 0, prompt)
        stdscr.refresh()
        user_input = stdscr.getstr().decode("utf-8")
        curses.noecho()
        return user_input

    if not scriptdir.exists():
        logger.info(f"Creating directory {scriptdir}")
        scriptdir.mkdir()

    # Check and create API token
    if not auth_token_file.exists():
        logger.warning(f"API token not found at {auth_token_file}")
        AUTH_TOKEN = get_user_input("Enter API token: ")
        auth_token_file.write_text(AUTH_TOKEN)
        auth_created = True

    if not csrf_token_file.exists():
        logger.warning(f"CSRF token not found at {csrf_token_file}")
        CSRF_TOKEN = get_user_input("Enter CSRF token: ")
        csrf_token_file.write_text(CSRF_TOKEN)
        csrf_created = True

    if auth_created or csrf_created:
        # Test the tokens
        stdscr.clear()
        stdscr.addstr(0, 0, "Testing tokens...")
        stdscr.refresh()

        workspace = Workspace()
        vms = workspace.get_workspaces(save=False)

        if vms is None:
            stdscr.clear()
            stdscr.addstr(
                0,
                0,
                "Error: Unable to retrieve workspaces. There might be an issue with your tokens.",
            )
            stdscr.addstr(
                2,
                0,
                "Tokens will be deleted. Check your tokens and press any key to try again...",
            )
            stdscr.refresh()
            stdscr.getch()
            stdscr.clear()

            # Delete token files if just created
            auth_token_file.unlink(missing_ok=True)
            csrf_token_file.unlink(missing_ok=True)

            # Recursive call to try again
            first_run(stdscr)
        elif auth_created or csrf_created:
            stdscr.clear()
            stdscr.addstr(0, 0, "Tokens verified successfully!")
            stdscr.addstr(2, 0, "Press any key to continue...")
            stdscr.refresh()
            stdscr.getch()
        else:
            logger.info("Tokens verified successfully!")


def main():
    workspace = Workspace()
    action = Action()
    data = workspace.get_workspaces(save=False)
    action("pause", data, [])


if __name__ == "__main__":
    main()
