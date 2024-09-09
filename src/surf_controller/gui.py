import curses
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from surf_controller.api import Action, Workspace, first_run
from surf_controller.utils import config, logger
from surf_controller import __version__

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
        self.usernamefile = self.scriptdir / config["files"]["username"]
        if self.usernamefile.exists():
            self.username = self.usernamefile.read_text().strip()
        else:
            logger.warning(f"Username not found at {self.usernamefile}")
            self.username = ""
        self.OUTPUT_FILE = self.scriptdir / config["files"]["ids"]
        self.workspace = Workspace()
        self.action = Action()
        self.vms: list = self.workspace.get_workspaces(save=True, username=self.username)
        self.current_row = 0
        self.current_page = 0
        self.selected = [False] * len(self.vms)

    def refresh(self) -> None:
        self.vms = self.workspace.get_workspaces(save=False, username=self.username)
        self.current_row = 0
        self.selected = [False] * len(self.vms)
        self.stdscr.refresh()

    def rename_user(self) -> None:
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, f"Current username: {self.username}")
        self.stdscr.addstr(2, 0, "Enter new username: ")
        self.stdscr.refresh()
        curses.echo()
        new_username = self.stdscr.getstr(2, 20).decode("utf-8")
        curses.noecho()
        if new_username:
            self.username = new_username
            self.usernamefile.write_text(new_username)
            self.show_status_message(f"Username updated to: {new_username}")
            logger.info(f"Username updated to: {new_username}")
        else:
            self.show_status_message("Username unchanged")

    def __call__(self, stdscr):
        self.stdscr = stdscr
        curses.start_color()

        # Define color pairs: (pair_number, foreground_color, background_color)
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK)

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
                if self.current_row < len(self.vms) - 1:
                    self.current_row += 1
                    # Go to the next page if necessary
                    if self.current_row >= (self.current_page + 1) * self.rows_per_page:
                        self.current_page += 1
            elif key == ord("J"):
                if self.current_page < self.max_pages:
                    self.current_page += 1
                    self.current_row = self.current_page * self.rows_per_page
            elif key == ord("k") and self.current_row > 0:
                if self.current_row > 0:
                    self.current_row -= 1
                    # Go to the previous page if necessary
                    if self.current_row < self.current_page * self.rows_per_page:
                        self.current_page -= 1
            elif key == ord("K"):
                if self.current_page > 0:
                    self.current_page -= 1
                    self.current_row = self.current_page * self.rows_per_page
            elif key == ord("\n"):  # Enter key
                self.selected[self.current_row] = not self.selected[self.current_row]
            elif key == ord("a"):  # Select all
                if all(self.selected):
                    self.selected = [False] * len(self.vms)
                else:
                    self.selected = [True] * len(self.vms)
            elif key == ord("f"):  # Filter VMs
                self.workspace.filter = not self.workspace.filter
                self.show_status_message(f"Toggle filtering for: {self.username}")
                self.refresh()
            elif key == ord("u"):  # Update VM list
                self.show_status_message("Updating VM list...\n")
                logger.info("Updated VM list...")
                self.refresh()
            elif key == ord("p"):
                idlist = [
                    self.vms[i].name for i in range(len(self.vms)) if self.selected[i]
                ]
                self.show_status_message(f"Pausing {idlist}...\n")
                self.action("pause", self.vms, idlist)
                time.sleep(5)
                self.refresh()
            elif key == ord("r"):  # Resume selected VMs
                idlist = [
                    self.vms[i].name for i in range(len(self.vms)) if self.selected[i]
                ]
                logger.info(f"Resuming {idlist}...\n")
                self.show_status_message(f"Resuming {idlist}...")

                self.action("resume", self.vms, idlist)
                time.sleep(5)
                self.refresh()
            elif key == ord("n"):  # Rename user
                self.rename_user()
            elif key == ord("l"):  # Toggle logs
                self.show_logs = not self.show_logs
            elif key == ord("s"):  # SSH into selected VM
                selected_vms = [vm for i, vm in enumerate(self.vms) if self.selected[i]]
                if len(selected_vms) == 1:
                    self.ssh_to_vm(selected_vms[0])
                elif len(selected_vms) > 1:
                    self.show_status_message("Please select only one VM for SSH")
                else:
                    self.show_status_message("No VM selected for SSH")
            elif key == ord("q"):  # Quit
                break
            self.print_menu()

    def print_menu(self) -> None:
        self.stdscr.clear()
        v = str(__version__)
        footlen = 10

        # Calculate the number of rows that can fit on the screen
        max_y, max_x = self.stdscr.getmaxyx()
        # Adjust for space taken by logs or footer
        self.rows_per_page = max_y - footlen - 12 if self.show_logs else max_y - footlen
        self.max_pages = len(self.vms) // self.rows_per_page

        footer_text = (
            f"== Username {'(filter)' if self.workspace.filter else ''}: {self.username}"
            f" == surfcontroller version {v} == Page {self.current_page + 1} of {self.max_pages + 1} ==\n"
            "Press \n'j' to move down, 'k' to move up,"
            "'J' to move to next page,'K' to move to previous page,\n"
            "'Enter' to select,'a' to select all,\n"
            "'f' to toggle filter,'n' to rename user,\n"
            "'p' to pause,'r' to resume,'u' to update status,"
            "'s' for ssh access,\n 'l' to toggle logs,'q' to quit\n"
        )
        footlen = len(footer_text.split('\n'))

        # Determine the current page's start and end indices
        start_index = self.current_page * self.rows_per_page
        end_index = min(start_index + self.rows_per_page, len(self.vms))

        # Display the VMs for the current page
        for idx in range(start_index, end_index):
            vm = self.vms[idx]
            mark = "[*] " if self.selected[idx] else "[ ] "
            status = "running" if vm.active else "paused"
            line = mark + vm.name + f"({status})"
            colornumber = 1 if vm.active else 4

            display_idx = idx - start_index  # Adjust index for display on current page
            if idx == self.current_row:
                try:
                    self.stdscr.addstr(display_idx, 0, line, curses.color_pair(2) | curses.A_REVERSE)

                    # self.stdscr.addstr(display_idx, 0, line, curses.A_REVERSE)
                except curses.error as e:
                    logger.debug(f"Error highlighting line {idx}: {line}, {e}")
            else:
                try:
                    self.stdscr.addstr(display_idx, 0, line, curses.color_pair(colornumber))
                except curses.error as e:
                    logger.debug(f"Error displaying line {idx}: {line}, {e}")

        # Display pagination and control information
        try:
            self.stdscr.addstr(self.rows_per_page, 0, footer_text)
        except curses.error as e:
            logger.debug(f"Error print menu: {e}")

        # Display logs if enabled
        if self.show_logs:
            try:
                self.stdscr.addstr(max_y - 12, 0, "===logs===")
                for idx, log in enumerate(self.logs[-10:]):
                    self.stdscr.addstr(max_y - 11 + idx, 0, log)
            except curses.error as e:
                logger.debug(f"Error displaying logs: {e}")

        self.stdscr.refresh()

    def show_status_message(self, message) -> None:
        try:
            self.stdscr.addstr(len(self.vms) + 1, 0, message)
        except curses.error as e:
            logger.debug(f"Error displaying status message: {e}")
        self.stdscr.refresh()
        time.sleep(2)  # Show the message for 2 seconds

    def ssh_to_vm(self, vm):
        if vm.ip:
            logger.info(f"Connecting to {vm.name} at {vm.ip}...")
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
                logger.info("SSH connection closed")
        else:
            self.show_status_message(f"No IP address available for {vm.name}")


def main():
    curses.wrapper(first_run)
    controller = Controller()
    curses.wrapper(controller)


if __name__ == "__main__":
    main()
