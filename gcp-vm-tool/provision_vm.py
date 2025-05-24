import argparse
import argparse
import os
import time
import google.cloud.compute_v1
from google.api_core.exceptions import GoogleAPIError # Import GoogleAPIError

# Constants
ZONE = "us-central1-a"
REGION = "us-central1"
MACHINE_TYPE_FULL = f"zones/{ZONE}/machineTypes/e2-medium"
VM_NAME_DEFAULT = "code-runner-vm"
SOURCE_IMAGE_FAMILY = "debian-11"
SOURCE_IMAGE_PROJECT = "debian-cloud"
RUNNER_REPO_URL = "https://github.com/sompaak/runner.git"
SERVICE_ACCOUNT_SCOPES = ['https://www.googleapis.com/auth/cloud-platform']
NETWORK_NAME = "global/networks/default"
TAGS = ["http-server", "https-server", "runner-5000"] # For firewall rules

def create_vm(project_id, zone, vm_name, machine_type_full, source_image_project, source_image_family, runner_repo_url, network_name, tags, service_account_scopes):
    """Creates a GCP VM instance with a startup script to deploy the runner app."""
    print(f"Attempting to create VM '{vm_name}' in project '{project_id}', zone '{zone}'...")

    instances_client = google.cloud.compute_v1.InstancesClient()
    operations_client = google.cloud.compute_v1.ZoneOperationsClient()

    # Define the systemd service file content
    # This needs to be carefully formatted and escaped for the startup script
    systemd_service_content = f"""\
[Unit]
Description=Sompaak Runner Service
After=network.target

[Service]
User=root
WorkingDirectory=/opt/runner
ExecStart=/opt/runner/venv/bin/python app/main.py
Restart=always
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    # Escape special characters for shell echo
    escaped_systemd_service_content = systemd_service_content.replace("`", "\\`").replace("$", "\\$").replace("!", "\\!")


    startup_script = f"""#!/bin/bash
set -e 
set -x # For debugging startup script issues

# 1. Update package lists
apt-get update -y

# 2. Install dependencies
apt-get install -y git python3 python3-pip python3-venv

# 3. Clone the runner
git clone {runner_repo_url} /opt/runner

# 4. Create venv
python3 -m venv /opt/runner/venv

# 5. Install runner app dependencies
/opt/runner/venv/bin/pip install -r /opt/runner/requirements.txt

# 6. Define the systemd service file content (already prepared in Python)
# 7. Write the systemd service file
# Using printf to handle multi-line content and special characters better than echo for this.
printf '%s' '{escaped_systemd_service_content}' > /etc/systemd/system/runner.service

# 8. Reload systemd
systemctl daemon-reload

# 9. Enable the service
systemctl enable runner.service

# 10. Start the service
systemctl start runner.service

echo "Startup script finished."
"""

    instance_config = {
        "name": vm_name,
        "machine_type": machine_type_full,
        "disks": [
            {
                "boot": True,
                "auto_delete": True,
                "initialize_params": {
                    "source_image": f"projects/{source_image_project}/global/images/family/{source_image_family}",
                    "disk_size_gb": "10", # Standard disk size
                },
            }
        ],
        "network_interfaces": [
            {
                "name": network_name,
                "access_configs": [{"name": "External NAT", "type_": "ONE_TO_ONE_NAT"}], # To get an external IP
                "can_ip_forward": False,
            }
        ],
        "tags": {"items": tags},
        "service_accounts": [
            {
                "email": "default", # Use the default service account
                "scopes": service_account_scopes,
            }
        ],
        "metadata": {
            "items": [
                {"key": "startup-script", "value": startup_script}
            ]
        },
    }

    print(f"Submitting VM creation request for '{vm_name}'...")
    try:
        operation = instances_client.insert_unary(
            project=project_id, zone=zone, instance_resource=instance_config
        )

        print(f"Waiting for VM creation operation {operation.name} to complete...")
        while operation.status != google.cloud.compute_v1.Operation.Status.DONE:
            time.sleep(10) # Poll every 10 seconds
            # The wait method will block until the operation is complete or the timeout is reached.
            # If the operation results in an error, it should raise an exception.
            operation = operations_client.wait(
                operation=operation.name, zone=zone, project=project_id # Default timeout is 120s
            )
            print(f"Operation status: {operation.status.name}")

        # After the loop, if operation.error exists, it means the operation completed with an error.
        # However, operations_client.wait() itself should raise an exception for most API errors.
        # This check is an additional safeguard.
        if hasattr(operation, 'error') and operation.error:
            print(f"Error during VM creation (after wait): {operation.error.message}") # Accessing error message
            # You might want to raise a custom exception here or re-raise a GoogleAPIError
            raise GoogleAPIError(f"VM creation failed: {operation.error.message}")


        print(f"VM '{vm_name}' created successfully.")
        instance = instances_client.get(project=project_id, zone=zone, instance=vm_name)
    
    except GoogleAPIError as e:
        print(f"An API error occurred while creating or waiting for the VM: {e}")
        print("Please check your GCP project permissions, quotas, and the provided parameters (project ID, zone, VM name, machine type, image).")
        print(f"Details: {e.message if hasattr(e, 'message') else str(e)}") # Print more details if available
        raise # Re-raise the exception to be caught by the main block's general handler if needed or to stop execution

    # Retrieve and print the external IP
    # This line is moved here as it should only run if the VM creation was successful
    # and no GoogleAPIError was raised before this point.
    # However, if get() also fails, it could raise GoogleAPIError, which should be handled.
    # For simplicity, we'll assume if creation succeeded, get() will too, or its error is acceptable to propagate.
    external_ip = instance.network_interfaces[0].access_configs[0].nat_i_p
    print(f"VM '{vm_name}' external IP: {external_ip}")
    return external_ip


if __name__ == "__main__":
    print("GCP VM Provisioning Script")
    print("--------------------------")
    print("Ensure GOOGLE_APPLICATION_CREDENTIALS environment variable is set.")
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        print("Error: The GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
        print("Please set it to the path of your GCP service account key file.")
        exit(1)

    parser = argparse.ArgumentParser(description="Provision a GCP VM to run the code runner application.")
    parser.add_argument("--project_id", help="Your Google Cloud project ID.", required=True)
    parser.add_argument("--vm_name", default=VM_NAME_DEFAULT, help=f"Name for the new VM (default: {VM_NAME_DEFAULT}).")
    
    args = parser.parse_args()

    print(f"Using Project ID: {args.project_id}")
    print(f"VM Name: {args.vm_name}")
    print(f"Zone: {ZONE}")
    print(f"Region: {REGION}")
    print(f"Machine Type: {MACHINE_TYPE_FULL}")
    print(f"Runner Repo URL: {RUNNER_REPO_URL}")
    print(f"Service Account Scopes: {SERVICE_ACCOUNT_SCOPES}")
    print(f"Network: {NETWORK_NAME}")
    print(f"Tags: {TAGS}")

    try:
        create_vm(
            project_id=args.project_id,
            zone=ZONE,
            vm_name=args.vm_name,
            machine_type_full=MACHINE_TYPE_FULL,
            source_image_project=SOURCE_IMAGE_PROJECT,
            source_image_family=SOURCE_IMAGE_FAMILY,
            runner_repo_url=RUNNER_REPO_URL,
            network_name=NETWORK_NAME,
            tags=TAGS,
            service_account_scopes=SERVICE_ACCOUNT_SCOPES,
        )
        print("\nProvisioning process completed successfully.")
    except GoogleAPIError:
        # This will catch errors re-raised from create_vm related to GCP API issues.
        # The specific error message would have already been printed in create_vm.
        print("\nProvisioning failed due to a GCP API error. Please review the messages above.")
    except Exception as e:
        print(f"\nAn unexpected error occurred during the provisioning process: {e}")
        print("Please check the script, logs, and your GCP project settings.")

    # Note: Firewall rule creation for 'runner-5000' tag (TCP port 5000)
    # is assumed to be handled manually or by another script for now.
    # Example gcloud command:
    # gcloud compute firewall-rules create allow-runner-5000 \
    # --network default \
    # --allow tcp:5000 \
    # --target-tags "runner-5000" \
    # --source-ranges "0.0.0.0/0" \
    # --description "Allow TCP traffic to port 5000 for runner VMs"
    # --project YOUR_PROJECT_ID
    print("\nReminder: Ensure firewall rule 'allow-runner-5000' exists for TCP port 5000, targeting the 'runner-5000' tag.")
