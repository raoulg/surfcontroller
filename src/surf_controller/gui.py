import curses
import threading
import time
from pathlib import Path
import subprocess

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
        self.vms = self.workspace.get_workspaces(save=True)
        self.current_row = 0
        self.selected = [False] * len(self.vms)
        self.stdscr = None

    def __call__(self, stdscr):
        self.stdscr = stdscr
        self.stdscr.clear()



        def update_logs():
            while True:
                with open(self.log_file, "r") as f:
                    new_logs = f.readlines()[-10:]
                with self.log_lock:
                    self.logs = new_logs
                time.sleep(1)  # Check for new logs every second

        log_thread = threading.Thread(target=update_logs, daemon=True)
        log_thread.start()

        self.print_menu()

        while True:
            key = self.stdscr.getch()
            if key == ord("j") and self.current_row < len(self.vms) - 1:
                self.current_row += 1
            elif key == ord("k") and self.current_row > 0:
                self.current_row -= 1
            elif key == ord("\n"):  # Enter key
                self.selected[self.current_row] = not self.selected[self.current_row]
            elif key == ord("a"):  # Select all
                if all(self.selected):
                    self.selected = [False] * len(self.vms)
                else:
                    self.selected = [True] * len(self.vms)
            elif key == ord("u"):  # Update VM list
                self.show_status_message("Updating VM list...\n")
                self.vms = self.workspace.get_workspaces(save=False)
                logger.info("Updated VM list...")
                self.selected = [False] * len(self.vms)
                self.stdscr.refresh()
            elif key == ord("p"):
                idlist = [self.vms[i].name for i in range(len(self.vms)) if self.selected[i]]
                self.show_status_message(f"Pausing {idlist}...\n")
                self.stdscr.addstr(2, 0, f"Pausing {idlist}")
                self.action("pause", self.vms, idlist)
                time.sleep(10)
                self.vms = self.workspace.get_workspaces(save=False)
                self.selected = [False] * len(self.vms)
                self.stdscr.refresh()
            elif key == ord("r"):  # Resume selected VMs
                idlist = [self.vms[i].name for i in range(len(self.vms)) if self.selected[i]]
                logger.info(f"Resuming {idlist}...\n")
                show_status_message(f"Resuming {idlist}...")

                self.action("resume", self.vms, idlist)
                time.sleep(10)
                self.vms = self.workspace.get_workspaces(save=False)
                self.selected = [False] * len(self.vms)
                self.stdscr.refresh()
            elif key == ord("l"):  # Toggle logs
                self.show_logs = not self.show_logs
            elif key == ord("s"):  # SSH into selected VM
                selected_vms = [vm for i, vm in enumerate(self.vms) if self.selected[i]]
                if len(selected_vms) == 1:
                    self.ssh_to_vm(selected_vms[0])
                elif len(selected_vms) > 1:
                    show_status_message("Please select only one VM for SSH")
                else:
                    show_status_message("No VM selected for SSH")
            elif key == ord("q"):  # Quit
                break
            self.print_menu()

    def print_menu(self) -> None:
        self.stdscr.clear()
        for idx, vm in enumerate(self.vms):
            mark = "[*] " if self.selected[idx] else "[ ] "
            status = "running" if vm.active else "paused"
            line = (
                mark + vm.name + f"({status})"
            )  # Combine the mark and the VM name

            if idx == self.current_row:
                self.stdscr.addstr(
                    idx, 0, line, curses.A_REVERSE
                )  # Highlight the entire line
            else:
                self.stdscr.addstr(idx, 0, line)  # Display the line without highlighting

        self.stdscr.addstr(
            idx + 2,
            0,
            "Press \n'j' to move down,\n 'k' to move up,\n'Enter' to select,"
            "\n 'a' to select all,\n 'p' to pause,\n 'r' to resume,\n 'u' to update status,"
            "\n's' for ssh access,\n 'l' to toggle logs,\n'q' to quit",
        )
        if self.show_logs:
            self.stdscr.addstr(len(self.vms) + 12, 0, "===logs===")
            for idx, log in enumerate(self.logs[-10:]):
                self.stdscr.addstr(len(self.vms) + 13 + idx, 0, log)
        self.stdscr.refresh()

    def show_status_message(self, message) -> None:
        self.stdscr.addstr(len(self.vms) + 12, 0, message)
        self.stdscr.refresh()
        time.sleep(2)  # Show the message for 2 seconds

    def ssh_to_vm(self, vm):
        if vm.ip:
            self.show_status_message(f"Connecting to {vm.name} at {vm.ip}...")
            ssh_command = f"ssh {vm.ip}"

            try:
                # Use curses.endwin() to temporarily suspend curses
                curses.endwin()
                subprocess.run(ssh_command, shell=True)
            except Exception as e:
                logger.error(f"SSH connection failed: {str(e)}")
            finally:
                # Reinitialize curses
                self.stdscr.refresh()
        else:
            self.show_status_message(f"No IP address available for {vm.name}")


def main():
    curses.wrapper(first_run)
    controller = Controller()
    curses.wrapper(controller)


if __name__ == "__main__":
    main()
