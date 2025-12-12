import csv
import curses
import shutil
import time
import json
from collections import namedtuple
from pathlib import Path
from typing import Optional

import requests

from surf_controller.setup import USER_CONFIG_DIR
from surf_controller.utils import config, logger

Data = namedtuple("Data", ["id", "name", "active", "ip", "exclude_pause", "end_date"])



class Action:
    def __init__(self):
        self.scriptdir = USER_CONFIG_DIR
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

    def __call__(self, do: str, data: list, id_filter: list, progress_callback=None):
        # Filter items first to know the total count
        items_to_process = []
        for item in data:
            if id_filter and item.name not in id_filter:
                continue
            items_to_process.append(item)
            
        total = len(items_to_process)
        for i, item in enumerate(items_to_process):
            if progress_callback:
                progress_callback(i + 1, total)
                
            timestamp = time.strftime("%d-%m-%Y %H:%M:%S")
            
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
        self.scriptdir = USER_CONFIG_DIR
        self.URL = (
            config["surf"]["URL"] + "/?application_type=Compute&deleted=false&limit=100"
        )
        self.auth_token_file = self.scriptdir / config["files"]["api-token"]
        if self.auth_token_file.exists():
            self.AUTH_TOKEN = self.auth_token_file.read_text().strip()
        else:
            logger.warning(f"API token not found at {self.auth_token_file}")
        self.OUTPUT_FILE = self.scriptdir / config["files"]["ids"]
        self.EXCLUSIONS_FILE = self.scriptdir / "exclusions.json"
        self.filter = False

        # Set up the headers for the request
        self.headers = {
            "accept": "application/json;Compute",
            "authorization": self.AUTH_TOKEN,
        }

    def load_exclusions(self) -> set:
        """Loads the set of excluded VM IDs from the JSON file."""
        if not self.EXCLUSIONS_FILE.exists():
            return set()
        try:
            with self.EXCLUSIONS_FILE.open("r") as f:
                excluded_ids = json.load(f)
                if isinstance(excluded_ids, list):
                    return set(excluded_ids)
                else:
                    logger.info(
                        f"Exclusions file {self.EXCLUSIONS_FILE} does not contain a list. Ignoring."
                    )
                    return set()
        except json.JSONDecodeError:
            logger.error(
                f"Error decoding JSON from {self.EXCLUSIONS_FILE}. Treating as empty."
            )
            return set()
        except Exception as e:
            logger.error(f"Error reading exclusions file {self.EXCLUSIONS_FILE}: {e}")
            return set()

    def save_exclusions(self, excluded_ids_set: set):
        """Saves the set of excluded VM IDs to the JSON file."""
        try:
            with self.EXCLUSIONS_FILE.open("w") as f:
                # Convert set back to list for JSON serialization
                json.dump(list(excluded_ids_set), f, indent=2)
            logger.info(f"Exclusion list saved to {self.EXCLUSIONS_FILE}")
        except Exception as e:
            logger.error(f"Error writing exclusions file {self.EXCLUSIONS_FILE}: {e}")

    def get_workspaces(
        self, save: bool = False, username: Optional[str] = None
    ) -> list:
        # Make the GET request
        excluded_ids_set = self.load_exclusions()
        response = requests.get(self.URL, headers=self.headers)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()
            if save:
                self.save(data)

            results = []
            
            for result in data["results"]:
                meta = result["resource_meta"]
                if "ip" in meta:
                    ip = meta["ip"]
                else:
                    ip = "Not available"
                
                end_date = result.get("end_time", "")
                
                if self.filter and username and username not in result["name"]:
                    continue
                vm_id = result["id"]
                exclude_pause_status = vm_id in excluded_ids_set
                results.append(
                    Data(
                        vm_id,
                        result["name"],
                        result["active"],
                        ip,
                        exclude_pause_status,
                        end_date,
                    )
                )
            return results
        else:
            logger.info(f"Failed to fetch data. Status code: {response.status_code}")
            return []

    def get_workspace(self, vm_id: str) -> Optional[namedtuple]:
        """Fetches data for a single workspace."""
        excluded_ids_set = self.load_exclusions()
        url = f"{config['surf']['URL']}/{vm_id}"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            result = response.json()
            
            
            meta = result.get("resource_meta", {})
            ip = meta.get("ip", "Not available")
            end_date = result.get("end_time", "")
            
            exclude_pause_status = vm_id in excluded_ids_set
            
            return Data(
                result["id"],
                result["name"],
                result["active"],
                ip,
                exclude_pause_status,
                end_date,
            )
        else:
            logger.error(f"Failed to fetch workspace {vm_id}. Status: {response.status_code}")
            return None

    def update_workspace(self, vm_id: str, data: dict) -> bool:
        """Updates a workspace with the given data."""
        url = f"{config['surf']['URL']}/{vm_id}/"
        response = requests.patch(url, headers=self.headers, json=data)
        
        if response.status_code == 200:
            logger.info(f"Successfully updated workspace {vm_id}")
            return True
        else:
            logger.error(f"Failed to update workspace {vm_id}. Status: {response.status_code}, Response: {response.text}")
            return False

    def create_workspace(self, data: dict) -> bool:
        """Creates a new workspace."""
        url = f"{config['surf']['URL']}/"
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code == 201: # Assuming 201 Created
            logger.info("Successfully created workspace")
            return True
        elif response.status_code == 200: # Sometimes APIs return 200
            logger.info("Successfully created workspace (200)")
            return True
        else:
            logger.error(f"Failed to create workspace. Status: {response.status_code}, Response: {response.text}")
            return False

    def delete_workspace(self, vm_id: str) -> bool:
        """Deletes a workspace by ID."""
        url = f"{config['surf']['URL']}/{vm_id}/"
        response = requests.delete(url, headers=self.headers)
        
        if response.status_code == 204: # No Content usually means success for DELETE
            logger.info(f"Successfully deleted workspace {vm_id}")
            return True
        elif response.status_code == 200:
            logger.info(f"Successfully deleted workspace {vm_id} (200)")
            return True
        else:
            logger.error(f"Failed to delete workspace {vm_id}. Status: {response.status_code}, Response: {response.text}")
            return False

    def save(self, data: dict):
        with self.OUTPUT_FILE.open("w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["id", "name", "active", "ip"])  # Write header
            for result in data["results"]:
                meta = result["resource_meta"]
                if "ip" in meta:
                    ip = meta["ip"]
                else:
                    ip = "Not available"
                writer.writerow(
                    [
                        result["id"],
                        result["name"],
                        result["active"],
                        ip,
                    ]
                )

        logger.info(f"Data successfully saved to {self.OUTPUT_FILE}")

    def load_from_cache(self) -> list:
        """Loads workspace data from the cached CSV file."""
        if not self.OUTPUT_FILE.exists():
            return []
            
        excluded_ids_set = self.load_exclusions()
        results = []
        try:
            with self.OUTPUT_FILE.open("r", newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Map CSV fields to Data namedtuple
                    vm_id = row["id"]
                    exclude_pause_status = vm_id in excluded_ids_set
                    # CSV might preserve strings, convert active to boolean
                    active = row["active"].lower() == 'true' if isinstance(row["active"], str) else bool(row["active"])
                    
                    results.append(
                        Data(
                            vm_id,
                            row["name"],
                            active,
                            row["ip"],
                            exclude_pause_status,
                            "", # End date not currently saved in CSV, maybe add later or fetch fresh
                        )
                    )
            logger.info(f"Loaded {len(results)} workspaces from cache")
            return results
        except Exception as e:
            logger.error(f"Failed to load from cache: {e}")
            return []



def first_run(stdscr: curses.window):
    scriptdir = USER_CONFIG_DIR
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

    username = scriptdir / config["files"]["username"]
    if not username.exists():
        USER = get_user_input("Enter your SURF username (lastnameInitialfirstname): ")
        username.write_text(USER)

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
    data = workspace.get_workspaces(save=True)
    logger.info(data)
    action("pause", data, [])


if __name__ == "__main__":
    main()
