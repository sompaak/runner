import os
import subprocess # Add to imports at the top of gcp_utils.py
from google.cloud import compute_v1
from google.api_core.exceptions import NotFound
from dotenv import load_dotenv
import logging

# Configure basic logging for the utility module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Fetch required configuration from environment variables
# These should be set in your .env file or system environment
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID')
TARGET_VM_ZONE = os.getenv('TARGET_VM_ZONE') # e.g., 'us-central1-a'
PROVISION_VM_SCRIPT_PATH = os.getenv('PROVISION_VM_SCRIPT_PATH')

def get_vm_status(vm_name):
    """
    Checks the status of a GCP VM.

    Args:
        vm_name (str): The name of the VM to check.

    Returns:
        tuple: (status_str, ip_address_str or None)
               Possible status_str values: 'RUNNING', 'TERMINATED', 'STOPPED', 'SUSPENDED', 'NOT_FOUND', 'ERROR'.
    """
    if not GCP_PROJECT_ID or not TARGET_VM_ZONE:
        logger.error("GCP_PROJECT_ID or TARGET_VM_ZONE environment variables are not set.")
        return "ERROR", "GCP configuration missing in environment."

    if not vm_name:
        logger.error("VM name not provided for status check.")
        return "ERROR", "VM name is required."

    try:
        instances_client = compute_v1.InstancesClient()
        instance = instances_client.get(
            project=GCP_PROJECT_ID,
            zone=TARGET_VM_ZONE,
            instance=vm_name
        )
        
        status = instance.status
        ip_address = None
        if instance.network_interfaces and len(instance.network_interfaces) > 0:
            if instance.network_interfaces[0].access_configs and len(instance.network_interfaces[0].access_configs) > 0:
                ip_address = instance.network_interfaces[0].access_configs[0].nat_ip
        
        logger.info(f"VM '{vm_name}' status: {status}, IP: {ip_address}")
        return status, ip_address

    except NotFound:
        logger.info(f"VM '{vm_name}' not found in project '{GCP_PROJECT_ID}' zone '{TARGET_VM_ZONE}'.")
        return "NOT_FOUND", None
    except Exception as e:
        logger.error(f"Error getting VM status for '{vm_name}': {e}")
        return "ERROR", str(e)

if __name__ == '__main__':
    # Example usage (for testing this module directly)
    # Ensure your .env file is populated and GOOGLE_APPLICATION_CREDENTIALS is set
    target_vm = os.getenv('TARGET_VM_NAME', 'code-runner-vm') # Get from .env or use default
    if not target_vm:
        print("TARGET_VM_NAME not set in .env for testing.")
    else:
        print(f"Checking status for VM: {target_vm} in project {GCP_PROJECT_ID}, zone {TARGET_VM_ZONE}")
        status, ip = get_vm_status(target_vm)
        print(f"Status: {status}, IP Address: {ip}")

    if PROVISION_VM_SCRIPT_PATH and GCP_PROJECT_ID:
       print("\nTesting VM creation trigger...")
       vm_to_create = os.getenv('TARGET_VM_NAME', 'test-creation-vm') # Use a different name for creation test
       # To avoid issues with existing VMs during test, you might want to use a unique name or ensure cleanup
       # For this example, we'll use the TARGET_VM_NAME or a default test name
       # Potentially add a suffix to make it unique for testing if needed
       # vm_to_create = f"{os.getenv('TARGET_VM_NAME', 'code-runner-vm')}-createtest" 

       # Before triggering creation, you might want to check if it already exists and decide action
       existing_status, _ = get_vm_status(vm_to_create)
       if existing_status == "RUNNING" or existing_status == "STOPPED": # or other non-NOT_FOUND states
           print(f"VM '{vm_to_create}' already exists with status '{existing_status}'. Skipping creation test for safety.")
           # Optionally, could delete it here if this is a dedicated test VM
           # For now, we just skip to avoid unintended modifications to existing VMs
       elif existing_status == "NOT_FOUND":
            print(f"VM '{vm_to_create}' not found, proceeding with creation test.")
            success, message = trigger_vm_creation(vm_to_create)
            print(f"Creation success: {success}, Message/IP: {message}")
            if success:
                print(f"To clean up, manually delete VM: {vm_to_create}")
       else: # ERROR or other states
           print(f"VM '{vm_to_create}' is in state '{existing_status}'. Skipping creation test.")
    else:
       print("\nSkipping VM creation trigger test: PROVISION_VM_SCRIPT_PATH or GCP_PROJECT_ID not set.")


def trigger_vm_creation(vm_name):
    """
    Triggers the creation of a GCP VM by calling the provision_vm.py script.

    Args:
        vm_name (str): The name for the new VM.

    Returns:
        tuple: (success_bool, message_or_ip_str)
               If successful, message_or_ip_str contains the new VM's IP address.
               If failed, message_or_ip_str contains an error message.
    """
    if not PROVISION_VM_SCRIPT_PATH:
        logger.error("PROVISION_VM_SCRIPT_PATH environment variable is not set.")
        return False, "Path to provisioning script is not configured."
    
    if not os.path.exists(PROVISION_VM_SCRIPT_PATH):
        logger.error(f"Provisioning script not found at: {PROVISION_VM_SCRIPT_PATH}")
        return False, f"Provisioning script not found at the configured path."

    if not GCP_PROJECT_ID: # Ensure project ID is available for the script call
        logger.error("GCP_PROJECT_ID environment variable is not set for provisioning.")
        return False, "GCP_PROJECT_ID is not configured for provisioning."

    command = [
        'python3', 
        PROVISION_VM_SCRIPT_PATH, 
        '--project_id', GCP_PROJECT_ID, 
        '--vm_name', vm_name
    ]

    try:
        logger.info(f"Executing VM provisioning script: {' '.join(command)}")
        # Using subprocess.run to capture output and wait for completion
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=300) # 5 min timeout
        
        output_lines = result.stdout.strip().split('\n')
        # Assuming the last line of successful output from provision_vm.py is the IP address
        # Example output from provision_vm.py: "VM created successfully. External IP: XXX.XXX.XXX.XXX"
        # Or simply just the IP: "XXX.XXX.XXX.XXX"
        ip_address = None
        for line in reversed(output_lines):
            if line.strip(): # Find the last non-empty line
                # Try to extract IP if it's in a sentence or is the line itself
                if "External IP:" in line:
                    ip_address = line.split("External IP:")[-1].strip()
                    break
                # Basic check if the line itself could be an IP (very rudimentary)
                elif len(line.strip().split('.')) == 4 and all(part.isdigit() or part == '*' for part in line.strip().split('.')):
                     # Basic check if the line itself could be an IP
                    ip_address = line.strip()
                    break
        
        if ip_address:
            logger.info(f"Provisioning script executed successfully. Output IP: {ip_address}")
            return True, ip_address
        else:
            logger.error(f"Provisioning script output did not contain expected IP address line. Full output:\n{result.stdout}")
            return False, "Provisioning script ran, but IP address could not be determined from output."

    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing provisioning script: {e}. Return code: {e.returncode}")
        logger.error(f"Stdout: {e.stdout}")
        logger.error(f"Stderr: {e.stderr}")
        return False, f"Error during VM provisioning: {e.stderr or e.stdout or 'Unknown error'}"
    except subprocess.TimeoutExpired as e:
        logger.error(f"Timeout executing provisioning script: {e}")
        return False, "VM provisioning script timed out."
    except Exception as e:
        logger.error(f"An unexpected error occurred while triggering VM creation: {e}")
        return False, f"An unexpected error occurred: {str(e)}"
