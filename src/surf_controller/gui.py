import curses
import threading
import time
from pathlib import Path

from surf_controller.api import Action, Workspace, first_run
from surf_controller.utils import config, logger


class Controller:
    def __init__(self):
        self.scriptdir = Path.home() / config["files"]["scriptdir"]
        self.log_file = self.scriptdir / "logs.log"
        self.show_logs = False
        self.logs = []
        self.log_lock = threading.Lock()
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
                "Press \n'j' to move down,\n 'k' to move up,\n'Enter' to select,"
                "\n 'a' to select all,\n 'p' to pause,\n 'r' to resume,\n 'u' to update status,"
                "\n'l' to toggle logs,\n'q' to quit",
            )
            if self.show_logs:
                stdscr.addstr(len(vms) + 12, 0, "===logs===")
                for idx, log in enumerate(self.logs[-10:]):
                    stdscr.addstr(len(vms) + 13 + idx, 0, log)
            stdscr.refresh()

        def show_status_message(message):
            stdscr.addstr(len(vms) + 10, 0, message)
            stdscr.refresh()
            time.sleep(2)  # Show the message for 2 seconds

        def update_logs():
            while True:
                with open(self.log_file, "r") as f:
                    new_logs = f.readlines()[-10:]
                with self.log_lock:
                    self.logs = new_logs
                time.sleep(1)  # Check for new logs every second

        log_thread = threading.Thread(target=update_logs, daemon=True)
        log_thread.start()

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
                show_status_message("Updating VM list...\n")
                vms = self.workspace.get_workspaces(save=False)
                logger.info("Updated VM list...")
                selected = [False] * len(vms)
                stdscr.refresh()
            elif key == ord("p"):
                idlist = [vms[i].name for i in range(len(vms)) if selected[i]]
                show_status_message(f"Pausing {idlist}...\n")
                stdscr.addstr(2, 0, f"Pausing {idlist}")
                self.action("pause", vms, idlist)
                time.sleep(10)
                vms = self.workspace.get_workspaces(save=False)
                selected = [False] * len(vms)
                stdscr.refresh()
            elif key == ord("r"):  # Resume selected VMs
                idlist = [vms[i].name for i in range(len(vms)) if selected[i]]
                logger.info(f"Resuming {idlist}...\n")
                show_status_message(f"Resuming {idlist}...")

                self.action("resume", vms, idlist)
                time.sleep(10)
                vms = self.workspace.get_workspaces(save=False)
                selected = [False] * len(vms)
                stdscr.refresh()
            elif key == ord("l"):  # Toggle logs
                self.show_logs = not self.show_logs
            elif key == ord("q"):  # Quit
                break
            print_menu()


def main():
    curses.wrapper(first_run)
    controller = Controller()
    curses.wrapper(controller)


if __name__ == "__main__":
    main()
