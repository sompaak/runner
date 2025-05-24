import pytest
import json
import os
from app.main import app, WORKSPACE_DIR

@pytest.fixture
def client():
    app.config['TESTING'] = True
    # Ensure WORKSPACE_DIR exists before tests, as app usually creates it on request
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    with app.test_client() as client:
        yield client
    # Optional: Clean up WORKSPACE_DIR after tests if needed,
    # but app/main.py should clean up individual files.
    # For a more robust cleanup, one might clear the WORKSPACE_DIR here.

def test_run_python_code_success(client):
    """Test successful Python code execution."""
    payload = {
        "code": "print('hello test')",
        "filename": "test_script.py",
        "language": "python"
    }
    response = client.post('/run_code', json=payload)
    assert response.status_code == 200
    response_data = json.loads(response.data)

    assert response_data['status'] == 'success'
    assert response_data['stdout'] == 'hello test\n'
    assert response_data['stderr'] == ''
    assert response_data['return_code'] == 0
    # WORKSPACE_DIR in main.py is './workspace', so we construct the path accordingly
    expected_script_path = os.path.join(WORKSPACE_DIR, "test_script.py")
    assert response_data['command_executed'] == ["python", expected_script_path]

def test_run_python_code_error(client):
    """Test Python code execution with an error."""
    payload = {
        "code": "import sys; sys.exit(1)",
        "filename": "error_script.py",
        "language": "python"
    }
    response = client.post('/run_code', json=payload)
    assert response.status_code == 200 # The HTTP request itself is successful
    response_data = json.loads(response.data)

    assert response_data['status'] == 'error'
    assert response_data['return_code'] != 0
    # Specific return code for sys.exit(1) is 1
    assert response_data['return_code'] == 1
    expected_script_path = os.path.join(WORKSPACE_DIR, "error_script.py")
    assert response_data['command_executed'] == ["python", expected_script_path]


def test_run_code_invalid_filename(client):
    """Test for invalid filename (directory traversal attempt)."""
    payload = {
        "code": "print('test')",
        "filename": "../evil_script.py",
        "language": "python"
    }
    response = client.post('/run_code', json=payload)
    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert "error" in response_data
    assert "Invalid filename" in response_data["error"]

def test_run_code_unsupported_language(client):
    """Test for unsupported language."""
    payload = {
        "code": "echo 'hello'",
        "filename": "script.sh",
        "language": "bash"
    }
    response = client.post('/run_code', json=payload)
    # Based on app/main.py, it returns 400 for unsupported language
    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert "error" in response_data
    assert "Unsupported language" in response_data["error"]
    assert "bash" in response_data["error"]

def test_run_code_missing_parameters(client):
    """Test for missing parameters (e.g., filename)."""
    payload = {"code": "print('test')"} # Missing filename
    response = client.post('/run_code', json=payload)
    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert "error" in response_data
    assert "Missing 'code' or 'filename'" in response_data["error"]

def test_run_code_missing_code_parameter(client):
    """Test for missing 'code' parameter."""
    payload = {"filename": "some_script.py"} # Missing code
    response = client.post('/run_code', json=payload)
    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert "error" in response_data
    assert "Missing 'code' or 'filename'" in response_data["error"]

def test_run_code_empty_payload(client):
    """Test for empty JSON payload."""
    response = client.post('/run_code', json={})
    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert "error" in response_data
    assert "Missing 'code' or 'filename'" in response_data["error"]

def test_run_code_invalid_json(client):
    """Test for non-JSON payload."""
    response = client.post('/run_code', data="this is not json")
    assert response.status_code == 400 # Flask handles non-JSON by default with 400 if request.get_json() fails
    response_data = json.loads(response.data) # Flask's default error for this is also JSON
    assert "error" in response_data
    assert "Invalid JSON payload" in response_data["error"] # This is the message from our app

def test_workspace_dir_creation_and_file_cleanup(client):
    """Test that the workspace directory is created and files are cleaned up."""
    payload = {
        "code": "print('cleanup test')",
        "filename": "cleanup_test_script.py",
        "language": "python"
    }
    script_path = os.path.join(WORKSPACE_DIR, payload['filename'])

    # Ensure file does not exist before test
    if os.path.exists(script_path):
        os.remove(script_path)

    response = client.post('/run_code', json=payload)
    assert response.status_code == 200

    # The file should be created during execution and then removed by the app's finally block.
    assert not os.path.exists(script_path), f"File {script_path} was not cleaned up after execution."

    # Check that WORKSPACE_DIR itself still exists
    assert os.path.exists(WORKSPACE_DIR)
