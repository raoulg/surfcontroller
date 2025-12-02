import logging
from surf_controller.api import Workspace, Action
from surf_controller.utils import logger

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import datetime
from pathlib import Path

def log_status(message):
    try:
        log_file = Path("/config/last_run.txt")
        timestamp = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        log_file.write_text(f"{timestamp} - {message}")
    except Exception as e:
        logger.error(f"Failed to write log file: {e}")

def run_pause_job():
    logger.info("Starting pause job...")
    
    workspace = Workspace()
    action = Action()
    
    # Fetch all VMs
    try:
        vms = workspace.get_workspaces(save=False)
    except Exception as e:
        logger.error(f"Failed to fetch VMs: {e}")
        log_status(f"FAILED: Could not fetch VMs ({e})")
        return
    
    # Load exclusions
    exclusions = workspace.load_exclusions()
    
    # Identify VMs to pause
    vms_to_pause = []
    vm_names_to_pause = []
    
    for vm in vms:
        if vm.active:
            if vm.id in exclusions:
                logger.info(f"Skipping {vm.name} ({vm.id}) - Excluded from schedule")
            else:
                vms_to_pause.append(vm)
                vm_names_to_pause.append(vm.name)
    
    if vms_to_pause:
        logger.info(f"Pausing {len(vms_to_pause)} VMs: {', '.join(vm_names_to_pause)}")
        try:
            action("pause", vms, vm_names_to_pause)
            logger.info("Pause job completed.")
            log_status(f"SUCCESS: Paused {len(vms_to_pause)} VMs")
        except Exception as e:
             logger.error(f"Error during pause action: {e}")
             log_status(f"FAILED: Error during pause ({e})")
    else:
        logger.info("No VMs to pause.")
        log_status("SUCCESS: No VMs to pause")

if __name__ == "__main__":
    run_pause_job()
