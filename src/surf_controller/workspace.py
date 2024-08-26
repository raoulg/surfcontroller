from pathlib import Path
import requests
import csv
import json
import tomllib
from utils import logger, config
from collections import namedtuple


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
                # results.append((result["id"], result["name"], result["active"]))
            return results
        else:
            logger.info(f"Failed to fetch data. Status code: {response.status_code}")
            return None

    def save(self, data):
        with self.OUTPUT_FILE.open("w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["id", "name", "active"])  # Write header
            for result in data["results"]:
                writer.writerow([result["id"], result["name"], result["active"]])

        logger.info(f"Data successfully saved to {self.OUTPUT_FILE}")


if __name__ == "__main__":
    workspace = Workspace()
    data = workspace.get_workspaces()
