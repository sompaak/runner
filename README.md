# GCP VM Runner

This project implements a simple Flask-based runner that can execute code on a GCP VM, triggered by an HTTP request. It's designed to receive code, save it to a file, execute it, and return the output. The executed commands are also shown in the response.

## Features

- Execute Python code snippets via an HTTP POST request.
- Securely saves code to a temporary file within a workspace.
- Captures and returns `stdout`, `stderr`, and the `return_code`.
- Displays the exact command executed.
- Basic protection against directory traversal.
- Logging for requests and operations.
- Includes unit tests.
- Dockerfile for easy containerization and deployment.

## Prerequisites

- Python 3.7+
- pip (Python package installer)
- Docker (optional, for containerized deployment)

## Local Setup & Running

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/sompaak/runner.git # Replace with your actual URL if different
    cd runner
    ```
2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Run the application:**
    ```bash
    python app/main.py
    ```
    The server will start on `http://0.0.0.0:5000`.

## Running with Docker

1.  **Build the Docker image:**
    ```bash
    docker build -t vm-runner .
    ```
2.  **Run the Docker container:**
    ```bash
    docker run -p 5000:5000 vm-runner
    ```
    The server will be accessible on `http://localhost:5000`.

## API Endpoint: `/run_code`

-   **Method:** `POST`
-   **Description:** Receives code, saves it to a file, executes it, and returns the output.
-   **Request Body (JSON):**
    ```json
    {
        "code": "print('Hello from the runner!')",
        "filename": "myscript.py",
        "language": "python" 
    }
    ```
    -   `code` (string, required): The code to execute.
    -   `filename` (string, required): The name for the temporary script file (e.g., `myscript.py`). Must be a simple filename without path components.
    -   `language` (string, optional, default: `"python"`): The language of the code. Currently, only `"python"` is supported.

-   **Success Response (200 OK):**
    ```json
    {
        "status": "success",
        "stdout": "Hello from the runner!\n",
        "stderr": "",
        "command_executed": ["python", "./workspace/myscript.py"],
        "return_code": 0
    }
    ```
-   **Error Responses:**
    -   `400 Bad Request`: If input is invalid (e.g., missing parameters, invalid filename, unsupported language). The JSON response will contain an `error` field with details.
    ```json
    {
        "error": "Missing 'code' or 'filename'"
    }
    ```
    -   Other errors might occur if the script itself fails execution, in which case `status` will be `"error"` and `stderr` may contain details.

## Example Usage (`curl`)

```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"code": "print(\"Hello, curl!\")", "filename": "curl_test.py"}' \
     http://localhost:5000/run_code
```
