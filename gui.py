import curses
from pathlib import Path
from datetime import datetime, timedelta
import subprocess
import csv
import time
from utils import logger, get_config


def get_modification_date(file_path):
    """
    Get the last modification date of a file using pathlib.

    :param file_path: Path to the file (str or Path object)
    :return: Modification date as a datetime object
    """
    path = Path(file_path)
    moddate = datetime.fromtimestamp(path.stat().st_mtime)
    return moddate < (datetime.now() - timedelta(days=1))


def run_script(script_path, args=None):
    """
    Run a .sh script from Python with optional arguments.

    :param script_path: Path to the .sh script (str or Path object)
    :param args: A list of additional arguments/flags to pass to the script (optional)
    :return: Output of the script as a string, or raises an exception if the script fails
    """
    if args is None:
        args = []

    try:
        # Combine the script path and the additional arguments
        command = ["bash", str(script_path)] + args

        # Run the script and capture the output
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        # If the script fails, capture the error and raise an exception
        raise RuntimeError(f"Script failed with error: {e.stderr}") from e


def load_file(file_path):
    """
    Load a CSV file and return each row as a tuple in a list.

    :param file_path: Path to the CSV file.
    :return: List of tuples, each representing a row in the CSV.
    """
    rows_as_tuples = []

    with open(file_path, mode="r", newline="") as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            rows_as_tuples.append(tuple(row))

    return rows_as_tuples


def main(stdscr):
    # Clear screen
    stdscr.clear()

    config = get_config()
    id_file = config["files"]["ids"]
    # mod = get_modification_date(id_file)
    # logger.info(f"File modified last 24h: {mod}")
    # if mod:
    res = run_script("workspace.sh").strip()
    logger.info(res)

    id_names = load_file(id_file)[1:]

    vms = []

    for vm in id_names:
        vmname = vm[1]
        if vm[2] == "true":
            status = "running"
        else:
            status = "paused"
        vms.append(f"{vmname} ({status})")

    # vms = [vm[1] for vm in id_names]
    logger.info(f"retrieved vms names: {vms}")

    # List of VM names
    selected = [False] * len(vms)
    current_row = 0

    def print_menu():
        stdscr.clear()
        for idx, vm in enumerate(vms):
            mark = "[*] " if selected[idx] else "[ ] "
            line = mark + vm  # Combine the mark and the VM name

            if idx == current_row:
                stdscr.addstr(
                    idx, 0, line, curses.A_REVERSE
                )  # Highlight the entire line
            else:
                stdscr.addstr(idx, 0, line)  # Display the line without highlighting
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
        elif key == ord("p"):  # Pause selected VMs (example)
            # Here you would call your pause function on selected VMs
            paused_vms = [id_names[i][0] for i in range(len(vms)) if selected[i]]
            idlist = ",".join(paused_vms)
            stdscr.addstr(2, 0, f"Pausing {idlist}")
            run_script("surf.sh", args=["--pause", f"--id={idlist}"])

            stdscr.refresh()
            stdscr.getch()  # Wait for another key press before exiting
        elif key == ord("r"):  # Resume selected VMs
            resumed_vms = [id_names[i][0] for i in range(len(vms)) if selected[i]]
            idlist = ",".join(resumed_vms)
            stdscr.addstr(2, 0, f"Resuming {idlist}")
            run_script("surf.sh", args=["--resume", f"--id={idlist}"])

            stdscr.refresh()
            stdscr.getch()  # Wait for another key press before exiting
        elif key == ord("q"):  # Quit
            break

        print_menu()


if __name__ == "__main__":
    curses.wrapper(main)
