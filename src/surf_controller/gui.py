import curses
import subprocess
import threading
import time
import json

from surf_controller.api import Action, Workspace, first_run
from surf_controller.utils import config, logger
from surf_controller.setup import USER_CONFIG_DIR, LOG_FILE
from surf_controller import __version__


class Controller:
    def __init__(self):
        self.scriptdir = USER_CONFIG_DIR
        self.log_file = LOG_FILE
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
        self.vms: list = self.workspace.get_workspaces(
            save=True, username=self.username
        )
        self.all_vms = self.vms
        self.current_row = 0
        self.current_page = 0
        self.selected = [False] * len(self.vms)
        self.excluded_ids = self.workspace.load_exclusions()
        
        # Filtering
        self.default_filters = ["UOS1", "UOS2", "UOS3"]
        if self.username:
            self.default_filters.append(self.username)
        
        self.FILTERS_FILE = self.scriptdir / "filters.json"
        self.custom_filters = []
        if self.FILTERS_FILE.exists():
            try:
                with open(self.FILTERS_FILE, "r") as f:
                    self.custom_filters = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load filters: {e}")

        self.active_filters = set()
        self.show_filter_input = False
        self.filter_running = False

        # Status
        self.status_message = ""
        self.status_type = "info" # info, success, error, busy
        self.last_refreshed = time.strftime("%H:%M:%S")

    def apply_filters(self):
        if not self.active_filters:
            self.vms = self.all_vms
        else:
            self.vms = []
            for vm in self.all_vms:
                for f in self.active_filters:
                    if f.lower() in vm.name.lower():
                        self.vms.append(vm)
                        break
        
        # Apply username filter if enabled (legacy filter)
        if self.workspace.filter and self.username:
             self.vms = [vm for vm in self.vms if self.username in vm.name]
             
        # Apply running filter
        if self.filter_running:
            self.vms = [vm for vm in self.vms if vm.active]

    def refresh(self) -> None:
        self.excluded_ids = self.workspace.load_exclusions()
        self.apply_filters()
        self.current_row = 0
        self.current_page = 0 # Reset page on refresh (filtering)
        self.selected = [False] * len(self.vms)
        self.stdscr.refresh()

    def fetch_all(self):
        self.all_vms = self.workspace.get_workspaces(save=False, username=self.username)
        self.last_refreshed = time.strftime("%H:%M:%S")
        self.refresh()

    def update_single_vm(self, vm_id: str):
        new_vm_data = self.workspace.get_workspace(vm_id)
        if new_vm_data:
            for i, vm in enumerate(self.all_vms):
                if vm.id == vm_id:
                    self.all_vms[i] = new_vm_data
                    break
            self.refresh()

    def rename_user(self) -> None:
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, f"Current username: {self.username}")
        self.stdscr.addstr(2, 0, "Enter new username: ")
        self.stdscr.refresh()
        curses.echo()
        new_username = self.stdscr.getstr(2, 20).decode("utf-8")
        curses.noecho()
        if new_username:
            # Update default filters: remove old username, add new one
            if self.username in self.default_filters:
                self.default_filters.remove(self.username)
                if self.username in self.active_filters:
                    self.active_filters.remove(self.username)
            
            self.username = new_username
            self.usernamefile.write_text(new_username)
            
            if new_username not in self.default_filters:
                self.default_filters.append(new_username)
                
            self.show_status_message(f"Username updated to: {new_username}")
            logger.info(f"Username updated to: {new_username}")
            self.refresh()
        else:
            self.show_status_message("Username unchanged")

    def draw_progress_bar(self, current, total, y_pos):
        height, width = self.stdscr.getmaxyx()
        bar_width = width - 10
        if bar_width < 10: bar_width = 10
        
        percent = current / total
        filled_len = int(bar_width * percent)
        
        # Thicker style
        bar = "#" * filled_len + "-" * (bar_width - filled_len)
        percent_str = f"{percent*100:.0f}%"
        
        try:
            self.stdscr.addstr(y_pos, 0, f"[{bar}] {percent_str}")
            self.stdscr.refresh()
        except curses.error:
            pass

    def batch_update_end_date(self):
        selected_indices = [i for i, s in enumerate(self.selected) if s]
        if not selected_indices:
            self.show_status_message("No VMs selected for update")
            return

        self.stdscr.clear()
        self.stdscr.addstr(0, 0, f"Updating end date for {len(selected_indices)} VMs")
        self.stdscr.addstr(2, 0, "Enter new end date (dd-mm-yyyy): ")
        curses.echo()
        date_str = self.stdscr.getstr(2, 32).decode("utf-8")
        curses.noecho()
        
        if not date_str:
            self.show_status_message("Update cancelled")
            self.refresh()
            return

        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, "%d-%m-%Y")
            now = datetime.now()
            if dt.date() < now.date():
                self.show_status_message("Error: Date cannot be in the past")
                self.refresh()
                return
            
            dt = dt.replace(hour=23, minute=59, second=59)
            iso_date = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            self.stdscr.clear()
            self.stdscr.addstr(0, 0, f"Updating {len(selected_indices)} VMs...")
            self.stdscr.refresh()
            
            success_count = 0
            total = len(selected_indices)
            
            for i, idx in enumerate(selected_indices):
                vm = self.vms[idx]
                self.stdscr.addstr(2 + i, 0, f"Updating {vm.name}...")
                self.stdscr.refresh()
                
                if self.workspace.update_workspace(vm.id, {"end_time": iso_date}):
                    self.stdscr.addstr(2 + i, 40, "OK", curses.color_pair(2))
                    success_count += 1
                    # Removed redundant update_single_vm to prevent glitches and speed up
                else:
                    self.stdscr.addstr(2 + i, 40, "FAILED", curses.color_pair(1))
                
                self.draw_progress_bar(i + 1, total, 2 + total + 1)
            
            self.stdscr.addstr(2 + total + 3, 0, f"Finished. Updated {success_count}/{total}. Press any key to continue.")
            self.stdscr.getch()
            
            # Auto-refresh
            self.fetch_all()
            self.show_status_message(f"Updated {success_count} VMs")
            
        except ValueError:
            self.show_status_message("Error: Invalid date format. Use dd-mm-yyyy")
        except Exception as e:
            self.show_status_message(f"Error: {e}")
            logger.error(f"Error updating end date: {e}")
        
        self.refresh()

    def delete_selected_vms(self):
        selected_indices = [i for i, s in enumerate(self.selected) if s]
        if not selected_indices:
            self.show_status_message("No VMs selected for deletion")
            return

        # Confirmation Dialog
        self.stdscr.clear()
        self.stdscr.addstr(2, 0, f"WARNING: You are about to DELETE {len(selected_indices)} VMs!", curses.color_pair(1) | curses.A_BOLD)
        self.stdscr.addstr(4, 0, "This action is IRREVERSIBLE.")
        self.stdscr.addstr(6, 0, "Are you sure? (y/n): ")
        self.stdscr.refresh()
        
        while True:
            key = self.stdscr.getch()
            if key == ord('y') or key == ord('Y'):
                break
            elif key == ord('n') or key == ord('N') or key == 27: # Esc
                self.show_status_message("Deletion cancelled")
                self.refresh()
                return
        
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, f"Deleting {len(selected_indices)} VMs...")
        self.stdscr.refresh()
        
        success_count = 0
        total = len(selected_indices)
        
        for i, idx in enumerate(selected_indices):
            vm = self.vms[idx]
            self.stdscr.addstr(2 + i, 0, f"Deleting {vm.name}...")
            self.stdscr.refresh()
            
            if self.workspace.delete_workspace(vm.id):
                self.stdscr.addstr(2 + i, 40, "OK", curses.color_pair(2))
                success_count += 1
            else:
                self.stdscr.addstr(2 + i, 40, "FAILED", curses.color_pair(1))
            
            self.draw_progress_bar(i + 1, total, 2 + total + 1)
            
        self.stdscr.addstr(2 + total + 3, 0, f"Finished. Deleted {success_count}/{total}. Press any key to continue.")
        self.stdscr.getch()
        
        # Refresh list
        self.fetch_all()
        self.show_status_message(f"Deleted {success_count} VMs")

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
            elif key == ord("\n") or key == ord(" "):  # Enter or Space key
                self.selected[self.current_row] = not self.selected[self.current_row]
            elif key == ord("a"):  # Select all
                if all(self.selected):
                    self.selected = [False] * len(self.vms)
                else:
                    self.selected = [True] * len(self.vms)
            elif key == ord("f"):  # Filter VMs (User)
                self.workspace.filter = not self.workspace.filter
                self.show_status_message(f"Toggle user filtering: {self.workspace.filter}")
                self.refresh()
            elif key == ord("R"): # Filter Running
                self.filter_running = not self.filter_running
                self.show_status_message(f"Toggle running filter: {self.filter_running}")
                self.refresh()
            
            # Filter Keys (Dynamic 1-9)
            elif ord("1") <= key <= ord("9"):
                idx = int(chr(key)) - 1
                all_filters = self.default_filters + self.custom_filters
                if idx < len(all_filters):
                    f = all_filters[idx]
                    if f in self.active_filters:
                        self.active_filters.remove(f)
                    else:
                        self.active_filters.add(f)
                    self.refresh()
            elif key == ord("+") or key == ord("="):
                self.add_custom_filter()

            elif key == ord("u"):  # Update VM list
                self.show_status_message("Updating VM list...")
                self.fetch_all()
                self.show_status_message("VM list updated.")
            
            elif key == ord("p"):
                idlist = [
                    self.vms[i].name for i in range(len(self.vms)) if self.selected[i]
                ]
                if idlist:
                    self.show_status_message(f"Pausing {len(idlist)} VMs...")
                    self.action("pause", self.vms, idlist)
                    
                    # Optimized update
                    for i in range(len(self.vms)):
                        if self.selected[i]:
                             self.update_single_vm(self.vms[i].id)
                    
                    self.show_status_message(f"Paused {len(idlist)} VMs.")
                else:
                    self.show_status_message("No VMs selected.")

            elif key == ord("r"):  # Resume selected VMs
                idlist = [
                    self.vms[i].name for i in range(len(self.vms)) if self.selected[i]
                ]
                if idlist:
                    self.show_status_message(f"Resuming {len(idlist)} VMs...")
                    self.action("resume", self.vms, idlist)
                    
                    # Optimized update
                    for i in range(len(self.vms)):
                        if self.selected[i]:
                             self.update_single_vm(self.vms[i].id)

                    self.show_status_message(f"Resumed {len(idlist)} VMs.")
                else:
                    self.show_status_message("No VMs selected.")

            elif key == ord("n"):  # Rename user
                self.rename_user()
            elif key == ord("E"): # Shift+e for exclusion
                self.toggle_pause_exclusion()
            elif key == ord("e"): # e for end date update
                self.batch_update_end_date()
            elif key == ord("c"): # c for creation wizard
                self.start_creation_wizard()
            elif key == ord("d"): # d for delete
                self.delete_selected_vms()
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
        max_y, max_x = self.stdscr.getmaxyx()

        # Layout configuration
        header_height = 2
        status_height = 3 # Status block
        filter_height = 3 # Filter block
        footer_height = 4 # Commands
        
        list_start_y = header_height + status_height + filter_height
        list_height = max_y - list_start_y - footer_height
        
        self.rows_per_page = list_height
        self.max_pages = max(0, (len(self.vms) - 1) // self.rows_per_page)

        # 1. Header
        header_text = f"SURF Controller v{v} | User: {self.username} | Last Refreshed: {self.last_refreshed} (u to update)"
        self.stdscr.addstr(0, 0, header_text, curses.A_BOLD)
        self.stdscr.hline(1, 0, curses.ACS_HLINE, max_x)

        # 2. Status Block
        status_title = "Status: "
        self.stdscr.addstr(2, 0, status_title, curses.A_BOLD)
        self.stdscr.addstr(2, len(status_title), self.status_message)
        # Clear status after display if it was temporary? For now keep it.
        
        # 3. Filter Block
        filter_title = "Filters: "
        self.stdscr.addstr(4, 0, filter_title, curses.A_BOLD)
        
        current_x = len(filter_title)
        
        # Combine default and custom filters for display and indexing
        all_filters = self.default_filters + self.custom_filters
        
        for idx, f in enumerate(all_filters):
            style = curses.color_pair(2) if f in self.active_filters else curses.color_pair(4)
            if f in self.active_filters:
                style = style | curses.A_REVERSE
            
            # Add number hint [N]
            filter_str = f"[{idx+1}:{f}] "
            self.stdscr.addstr(4, current_x, filter_str, style)
            current_x += len(filter_str)
            
        self.stdscr.addstr(4, current_x, "[+] Add Filter", curses.color_pair(4))
        
        if self.filter_running:
             self.stdscr.addstr(4, current_x + 15, "[R: Running Only]", curses.color_pair(2) | curses.A_REVERSE)

        self.stdscr.hline(list_start_y - 1, 0, curses.ACS_HLINE, max_x)

        # 4. VM List
        start_index = self.current_page * self.rows_per_page
        end_index = min(start_index + self.rows_per_page, len(self.vms))

        if not self.vms:
            self.stdscr.addstr(list_start_y, 0, "No VMs found matching filters.")
        else:
            from datetime import datetime, timedelta
            now = datetime.now()
            
            for idx in range(start_index, end_index):
                vm = self.vms[idx]
                mark = "[*] " if self.selected[idx] else "[ ] "
                status = "running" if vm.active else "paused"
                
                # Calculate expiration
                is_expiring_soon = False
                end_date_str = ""
                if vm.end_date:
                    try:
                        # Parse "2025-12-03T13:47:31.962000Z"
                        # Handle potential variations or Z
                        dt_str = vm.end_date.replace("Z", "+00:00")
                        end_dt = datetime.fromisoformat(dt_str)
                        # Remove timezone for comparison if needed, or make now aware
                        # Assuming simple comparison is enough or strip tz
                        if end_dt.tzinfo:
                            end_dt = end_dt.replace(tzinfo=None) # naive comparison
                        
                        days_left = (end_dt - now).days
                        if days_left <= 7:
                            is_expiring_soon = True
                        
                        end_date_str = f" [Ends: {end_dt.strftime('%Y-%m-%d')}]"
                    except Exception as e:
                        logger.debug(f"Error parsing date {vm.end_date}: {e}")

                base_line = mark + vm.name + f" ({status})" + end_date_str
                is_excluded = getattr(vm, "exclude_pause", False)
                exclusion_mark = " [NO PAUSE]" if is_excluded else ""
                line = base_line + exclusion_mark
                
                # Color Logic
                # Active: Green (2)
                # Paused: Grey (White/Dim - 4)
                # Expiring Soon: Red (1) - Overrides others? User said "make the machines that will enid within 7 days red"
                
                if is_expiring_soon:
                    color = curses.color_pair(1) # Red
                elif vm.active:
                    color = curses.color_pair(2) # Green
                else:
                    color = curses.color_pair(4) | curses.A_DIM # Grey/Dim White
                
                display_idx = list_start_y + (idx - start_index)
                
                if idx == self.current_row:
                    self.stdscr.addstr(display_idx, 0, line, color | curses.A_REVERSE)
                else:
                    self.stdscr.addstr(display_idx, 0, line, color)

        # 5. Footer (Commands)
        footer_y = max_y - footer_height
        self.stdscr.hline(footer_y - 1, 0, curses.ACS_HLINE, max_x)
        
        commands = [
            "j/k: Move", "J/K: Page", "Space/Enter: Select", "a: Select All",
            "p: Pause", "r: Resume", "u: Update",
            f"1-{len(all_filters)}: Toggle Filters", "+: Add Filter",
            "f: Toggle User Filter", "n: Rename User", "e: End Date", "E: Exclude",
            "c: Create VMs", "d: Delete VMs", "R: Running Only", "s: SSH", "l: Logs", "q: Quit"
        ]
        
        command_str = " | ".join(commands)
        
        # Auto-wrap logic
        current_line = ""
        line_idx = 0
        separator = " | "
        
        for cmd in commands:
            # Check if adding the next command would exceed the width
            if len(current_line) + len(separator) + len(cmd) < max_x:
                if current_line:
                    current_line += separator
                current_line += cmd
            else:
                # Print current line and start a new one
                self.stdscr.addstr(footer_y + line_idx, 0, current_line)
                line_idx += 1
                current_line = cmd
                # Stop if we run out of vertical space (reserve 1 line for page info)
                if line_idx >= footer_height - 1:
                    break 
        
        # Print the last line of commands
        if current_line and line_idx < footer_height - 1:
             self.stdscr.addstr(footer_y + line_idx, 0, current_line)
             line_idx += 1
        
        page_info = f"Page {self.current_page + 1}/{self.max_pages + 1}"
        self.stdscr.addstr(footer_y + line_idx, 0, page_info)

        # Display logs if enabled
        if self.show_logs:
            # Overlay logs? Or replace list?
            # Let's overlay at the bottom of the list area
            log_start_y = max_y - 12
            self.stdscr.addstr(log_start_y, 0, "=== LOGS ===", curses.A_BOLD)
            for idx, log in enumerate(self.logs[-10:]):
                if log_start_y + 1 + idx < max_y:
                     self.stdscr.addstr(log_start_y + 1 + idx, 0, log.strip())

        self.stdscr.refresh()

    def show_status_message(self, message) -> None:
        self.status_message = message
        try:
            # Update status line (row 2)
            self.stdscr.move(2, 0)
            self.stdscr.clrtoeol()
            self.stdscr.addstr(2, 0, "Status: ", curses.A_BOLD)
            self.stdscr.addstr(2, 8, message)
            self.stdscr.refresh()
        except curses.error as e:
            logger.debug(f"Error displaying status message: {e}")

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

    def start_creation_wizard(self):
        wizard = CreationWizard(self.stdscr, self.workspace, self.scriptdir)
        wizard.run()
        self.refresh()


class CreationWizard:
    def __init__(self, stdscr, workspace, scriptdir):
        self.stdscr = stdscr
        self.workspace = workspace
        self.scriptdir = scriptdir
        self.step = 0
        self.users_file = None
        self.template_file = None
        self.project_prefix = ""
        self.end_date = ""
        self.parsed_users = []
        self.template_data = {}

    def run(self):
        while True:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()
            
            # Title
            title = "Bulk VM Creation Wizard"
            self.stdscr.addstr(0, 0, title, curses.A_BOLD)
            self.stdscr.hline(1, 0, curses.ACS_HLINE, width)
            
            action = None
            if self.step == 0:
                action = self.step_select_user_file(height, width)
            elif self.step == 1:
                action = self.step_select_template_file(height, width)
            elif self.step == 2:
                action = self.step_options(height, width)
            elif self.step == 3:
                action = self.step_review(height, width)
            elif self.step == 4:
                action = self.step_creation(height, width)
                break # Exit after creation
            
            if action == 'quit' or self.step == -1:
                break
            
    def step_select_user_file(self, height, width):
        self.stdscr.addstr(2, 0, "Step 1: Select User File (users/)")
        
        users_dir = self.scriptdir.parent.parent / "users" # Assuming structure
        # Better: use config or relative path from cwd
        # User said "users/" folder. Let's assume it's in CWD or project root.
        # scriptdir is USER_CONFIG_DIR. 
        # Let's try CWD/users first
        import os
        cwd = os.getcwd()
        users_path = os.path.join(cwd, "users")
        
        if not os.path.exists(users_path):
             self.stdscr.addstr(4, 0, f"Error: 'users' directory not found at {users_path}")
             self.stdscr.addstr(6, 0, "Press any key to exit...")
             self.stdscr.getch()
             self.step = -1 # Exit
             return 'quit'

        files = [f for f in os.listdir(users_path) if f.endswith(".txt")]
        
        if not files:
            self.stdscr.addstr(4, 0, "No .txt files found in users/")
            self.stdscr.getch()
            self.step = -1
            return 'quit'
            
        current_selection = 0
        
        while True:
            for idx, f in enumerate(files):
                if idx == current_selection:
                    self.stdscr.addstr(4 + idx, 0, f"> {f}", curses.A_REVERSE)
                else:
                    self.stdscr.addstr(4 + idx, 0, f"  {f}")
            
            # Preview content
            preview_y = 4
            preview_x = 40
            
            # Clear preview area
            for i in range(height - preview_y - 2):
                self.stdscr.move(preview_y + i, preview_x)
                self.stdscr.clrtoeol()

            self.stdscr.addstr(preview_y - 1, preview_x, "File Content Preview:")
            try:
                with open(os.path.join(users_path, files[current_selection]), "r") as f:
                    lines = f.readlines()[:20] # Show more lines
                    for i, line in enumerate(lines):
                        if preview_y + i < height - 2:
                            self.stdscr.addstr(preview_y + i, preview_x, line.strip()[:40])
            except:
                pass

            self.stdscr.addstr(height - 2, 0, "UP/DOWN/j/k: Select | ENTER: Confirm | q: Quit")
            
            key = self.stdscr.getch()
            if key == ord('q'):
                self.step = -1 # Exit loop in run() needs to handle this
                return 'quit'
            elif (key == curses.KEY_UP or key == ord('k')) and current_selection > 0:
                current_selection -= 1
            elif (key == curses.KEY_DOWN or key == ord('j')) and current_selection < len(files) - 1:
                current_selection += 1
            elif key == ord('\n'):
                self.users_file = os.path.join(users_path, files[current_selection])
                self.step += 1
                return 'next'
    
    def step_select_template_file(self, height, width):
        self.stdscr.addstr(2, 0, "Step 2: Select Template File (templates/)")
        
        import os
        cwd = os.getcwd()
        templates_path = os.path.join(cwd, "templates")
        
        files = [f for f in os.listdir(templates_path) if f.endswith(".json")]
        
        current_selection = 0
        
        while True:
            for idx, f in enumerate(files):
                if idx == current_selection:
                    self.stdscr.addstr(4 + idx, 0, f"> {f}", curses.A_REVERSE)
                else:
                    self.stdscr.addstr(4 + idx, 0, f"  {f}")
            
            # Preview content
            preview_y = 4
            preview_x = 40
            
            # Clear preview area
            for i in range(height - preview_y - 2):
                self.stdscr.move(preview_y + i, preview_x)
                self.stdscr.clrtoeol()

            self.stdscr.addstr(preview_y - 1, preview_x, "Template Preview:")
            try:
                with open(os.path.join(templates_path, files[current_selection]), "r") as f:
                    lines = f.readlines()[:20]
                    for i, line in enumerate(lines):
                        if preview_y + i < height - 2:
                            self.stdscr.addstr(preview_y + i, preview_x, line.strip()[:40])
            except:
                pass

            self.stdscr.addstr(height - 2, 0, "UP/DOWN/j/k: Select | ENTER: Confirm | b: Back | q: Quit")
            
            key = self.stdscr.getch()
            if key == ord('q'):
                self.step = -1
                return 'quit'
            elif key == ord('b'):
                self.step -= 1
                return 'back'
            elif (key == curses.KEY_UP or key == ord('k')) and current_selection > 0:
                current_selection -= 1
            elif (key == curses.KEY_DOWN or key == ord('j')) and current_selection < len(files) - 1:
                current_selection += 1
            elif key == ord('\n'):
                self.template_file = os.path.join(templates_path, files[current_selection])
                self.step += 1
                return 'next'

    def step_options(self, height, width):
        self.stdscr.addstr(2, 0, "Step 3: Options")
        
        curses.echo()
        self.stdscr.addstr(4, 0, "Enter Project Prefix (e.g. UOS2): ")
        if self.project_prefix:
             self.stdscr.addstr(4, 34, self.project_prefix)
        else:
             self.project_prefix = self.stdscr.getstr(4, 34).decode("utf-8")
        
        self.stdscr.addstr(6, 0, "Enter End Date (dd-mm-yyyy): ")
        if self.end_date:
             self.stdscr.addstr(6, 29, self.end_date)
        else:
             self.end_date = self.stdscr.getstr(6, 29).decode("utf-8")
        curses.noecho()
        
        self.stdscr.addstr(height - 2, 0, "ENTER: Confirm | b: Back | q: Quit")
        
        # Validate date
        try:
            from datetime import datetime
            datetime.strptime(self.end_date, "%d-%m-%Y")
        except ValueError:
            self.stdscr.addstr(8, 0, "Invalid date format!", curses.color_pair(1))
            self.end_date = "" # Reset
            self.stdscr.getch()
            return 'retry'

        key = self.stdscr.getch()
        if key == ord('q'):
            self.step = -1
            return 'quit'
        elif key == ord('b'):
            self.project_prefix = "" # Reset for re-entry
            self.end_date = ""
            self.step -= 1
            return 'back'
        elif key == ord('\n'):
            self.step += 1
            return 'next'

    def step_review(self, height, width):
        self.stdscr.addstr(2, 0, "Step 4: Review")
        
        self.stdscr.addstr(4, 0, f"User File: {self.users_file}")
        self.stdscr.addstr(5, 0, f"Template: {self.template_file}")
        self.stdscr.addstr(6, 0, f"Project: {self.project_prefix}")
        self.stdscr.addstr(7, 0, f"End Date: {self.end_date}")
        
        # Parse users and show count
        with open(self.users_file, 'r') as f:
            self.parsed_users = [line.strip() for line in f if line.strip()]
            
        self.stdscr.addstr(9, 0, f"Total VMs to create: {len(self.parsed_users)}")
        
        self.stdscr.addstr(height - 2, 0, "ENTER: Create VMs | b: Back | q: Quit")
        
        key = self.stdscr.getch()
        if key == ord('q'):
            self.step = -1
            return 'quit'
        elif key == ord('b'):
            self.step -= 1
            return 'back'
        elif key == ord('\n'):
            self.step += 1
            return 'next'

    def step_creation(self, height, width):
        self.stdscr.addstr(2, 0, "Creating VMs...")
        
        import json
        from datetime import datetime
        
        with open(self.template_file, 'r') as f:
            template = json.load(f)
            
        # Parse date
        dt = datetime.strptime(self.end_date, "%d-%m-%Y")
        dt = dt.replace(hour=23, minute=59, second=59)
        iso_date = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        success_count = 0
        total = len(self.parsed_users)
        
        for idx, email in enumerate(self.parsed_users):
            username = email.split('@')[0].replace('.', '')
            
            # Name: PROJECT-USERNAME
            vm_name = f"{self.project_prefix}-{username}"
            
            # Hostname: projectusername (lowercase)
            hostname = f"{self.project_prefix}{username}".lower()
            
            # Prepare data
            data = template.copy()
            data['name'] = vm_name
            data['end_time'] = iso_date
            if 'meta' in data:
                data['meta']['host_name'] = hostname
            
            self.stdscr.addstr(4 + idx, 0, f"Creating {vm_name}...")
            self.stdscr.refresh()
            
            if self.workspace.create_workspace(data):
                self.stdscr.addstr(4 + idx, 40, "OK", curses.color_pair(2))
                success_count += 1
            else:
                self.stdscr.addstr(4 + idx, 40, "FAILED", curses.color_pair(1))
            
            self.stdscr.refresh()
            
        self.stdscr.addstr(height - 2, 0, f"Finished. Created {success_count}/{total}. Press any key to exit.")
        self.stdscr.getch()


def main():
    curses.wrapper(first_run)
    controller = Controller()
    curses.wrapper(controller)


if __name__ == "__main__":
    main()
