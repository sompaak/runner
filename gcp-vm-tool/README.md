# GCP VM Provisioning Tool

This tool provides a Python script (`provision_vm.py`) to automate the creation and configuration of a Google Cloud Platform (GCP) Virtual Machine. The VM is configured to run the `sompaak/runner` application (cloned from `https://github.com/sompaak/runner.git`) as a systemd service.

## Features

- Creates a new GCP VM instance (Debian 11, e2-medium by default).
- Sets up the `sompaak/runner` application:
    - Clones the repository from GitHub.
    - Installs Python dependencies in a virtual environment.
    - Configures and starts the runner as a systemd service.
- Configures firewall tags on the VM (http-server, https-server, runner-5000).
- Outputs the external IP address of the newly created VM.

## Prerequisites

1.  **Python 3.7+** and `pip`.
2.  **Google Cloud SDK:** Installed and configured (run `gcloud init`).
3.  **Service Account Key:**
    -   A GCP service account with permissions to create VMs and manage Compute Engine resources (e.g., roles like "Compute Instance Admin (v1)").
    -   The service account key file (JSON) downloaded to your local machine.
4.  **Environment Variable:** The `GOOGLE_APPLICATION_CREDENTIALS` environment variable must be set to the absolute path of your service account key JSON file.
    ```bash
    export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
    ```
5.  **GCP Project:**
    - Billing enabled for your GCP project.
    - The Compute Engine API must be enabled for your project. You can do this via the GCP console or `gcloud services enable compute.googleapis.com`.

## Setup

1.  **Clone this repository (gcp-vm-tool):**
    ```bash
    # If this tool were in its own repository:
    # git clone <gcp-vm-tool_repository_url>
    # cd gcp-vm-tool
    ```
    (For now, assume you are in the `gcp-vm-tool` directory containing `provision_vm.py`)

2.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the `provision_vm.py` script with your GCP Project ID:

```bash
python provision_vm.py --project_id YOUR_PROJECT_ID [--vm_name my-custom-vm-name]
```

**Arguments:**

-   `--project_id YOUR_PROJECT_ID`: (Required) Your Google Cloud Project ID.
-   `--vm_name my-custom-vm-name`: (Optional) A custom name for the VM. Defaults to `code-runner-vm`.

## Expected Outcome

-   The script will create a new GCP VM instance.
-   It will output the external IP address of this VM.
-   The `sompaak/runner` application will be running as a `systemd` service on the VM and accessible on port 5000 of the VM's external IP (e.g., `http://<EXTERNAL_IP>:5000`).

## Firewall Configuration

The script assigns the following network tags to the VM: `http-server`, `https-server`, `runner-5000`.

You **must** ensure that you have corresponding firewall rules in your GCP project's VPC network that allow ingress traffic for these tags. At a minimum, you need a rule for the `runner-5000` tag to allow TCP traffic on port 5000 from your desired source IP range (e.g., your IP address or `0.0.0.0/0` for public access - use with caution).

Example `gcloud` command to create a firewall rule for the runner:
```bash
gcloud compute firewall-rules create allow-runner-port-5000 \
    --network default \
    --action allow \
    --direction ingress \
    --rules tcp:5000 \
    --target-tags runner-5000 \
    --source-ranges 0.0.0.0/0 # Or your specific IP range
```

## Troubleshooting

-   **Permissions Errors:** Ensure your service account has the "Compute Instance Admin (v1)" role or equivalent permissions.
-   **API Not Enabled:** Make sure the Compute Engine API is enabled in your GCP project.
-   **Startup Script Issues:** If the VM is created but the runner isn't working, you can check the startup script logs:
    - Connect to the VM via SSH.
    - Check systemd service status: `sudo systemctl status runner.service`
    - View logs: `sudo journalctl -u runner.service -f`
    - Startup script output can also be found in `/var/log/daemon.log` or by inspecting the serial port output in the GCP console.
```
