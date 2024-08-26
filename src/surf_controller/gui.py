import curses
from pathlib import Path
import time

from utils import logger, config
from api import Workspace, Action, first_run


class Controller:
    def __init__(self):
        self.scriptdir = Path.home() / config["files"]["scriptdir"]
        self.URL = config["surf"]["URL"] + "/?application_type=Compute&deleted=false"
        self.auth_token_file = self.scriptdir / config["files"]["api-token"]
        if self.auth_token_file.exists():
            self.AUTH_TOKEN = self.auth_token_file.read_text().strip()
        else:
            logger.warning(f"API token not found at {self.auth_token_file}")
        self.OUTPUT_FILE = self.scriptdir / config["files"]["ids"]
        self.workspace = Workspace()
        self.action = Action()

    def __call__(self, stdscr):
        stdscr.clear()
        vms = self.workspace.get_workspaces(save=True)
        selected = [False] * len(vms)
        current_row = 0

        def print_menu():
            stdscr.clear()
            for idx, vm in enumerate(vms):
                mark = "[*] " if selected[idx] else "[ ] "
                status = "running" if vm.active else "paused"
                line = (
                    mark + vm.name + f"({status})"
                )  # Combine the mark and the VM name

                if idx == current_row:
                    stdscr.addstr(
                        idx, 0, line, curses.A_REVERSE
                    )  # Highlight the entire line
                else:
                    stdscr.addstr(idx, 0, line)  # Display the line without highlighting

            stdscr.addstr(
                idx + 2,
                0,
                "Press \n'j' to move down,\n 'k' to move up,\n'Enter' to select,\n 'a' to select all,\n 'p' to pause,\n 'r' to resume,\n 'u' to update status,\n 'q' to quit",
            )
            stdscr.refresh()

        print_menu()

        while True:
            key = stdscr.getch()
            if key == ord("j") and current_row < len(vms) - 1:
                current_row += 1
            elif key == ord("k") and current_row > 0:
                current_row -= 1
            elif key == ord("\n"):  # Enter key
                selected[current_row] = not selected[current_row]
            elif key == ord("a"):  # Select all
                selected = [True] * len(vms)
            elif key == ord("u"):  # Update VM list
                stdscr.addstr(2, 0, "Updating VM list...")
                vms = self.workspace.get_workspaces(save=False)
                logger.info("Updated VM list...")
                selected = [False] * len(vms)
                stdscr.refresh()
            elif key == ord("p"):
                idlist = [vms[i].name for i in range(len(vms)) if selected[i]]
                logger.info(f"Pausing {idlist}")
                stdscr.addstr(2, 0, f"Pausing {idlist}")
                self.action("pause", vms, idlist)
                time.sleep(10)
                vms = self.workspace.get_workspaces(save=False)
                selected = [False] * len(vms)
                stdscr.refresh()
            elif key == ord("r"):  # Resume selected VMs
                idlist = [vms[i].name for i in range(len(vms)) if selected[i]]
                logger.info(f"Resuming {idlist}")
                stdscr.addstr(2, 0, f"Resuming {idlist}")

                self.action("resume", vms, idlist)
                time.sleep(10)
                vms = self.workspace.get_workspaces(save=False)
                selected = [False] * len(vms)
                stdscr.refresh()
            elif key == ord("q"):  # Quit
                break
            print_menu()


if __name__ == "__main__":
    curses.wrapper(first_run)
    controller = Controller()
    curses.wrapper(controller)
