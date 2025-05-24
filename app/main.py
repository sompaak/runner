import os
import subprocess
import logging
from flask import Flask, request, jsonify

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

WORKSPACE_DIR = "./workspace"

@app.route('/run_code', methods=['POST'])
def run_code_route():
    os.makedirs(WORKSPACE_DIR, exist_ok=True)

    data = request.get_json()
    if not data:
        logging.error("Invalid JSON payload received.")
        return jsonify({"error": "Invalid JSON payload"}), 400

    code = data.get('code')
    filename = data.get('filename')
    language = data.get('language', 'python')

    logging.info(f"Received request to /run_code for filename: {filename}, language: {language}")

    if not code or not filename:
        logging.error(f"Missing 'code' or 'filename' in request. Filename: {filename}")
        return jsonify({"error": "Missing 'code' or 'filename'"}), 400

    # Security check for filename
    if os.path.basename(filename) != filename or '..' in filename:
        logging.error(f"Invalid filename (directory traversal attempt detected): {filename}")
        return jsonify({"error": "Invalid filename. Directory traversal attempt detected."}), 400

    full_file_path = os.path.join(WORKSPACE_DIR, filename)

    try:
        with open(full_file_path, 'w') as f:
            f.write(code)
        logging.info(f"Code written to {full_file_path}")
    except IOError as e:
        logging.error(f"Failed to write code to file {full_file_path}: {str(e)}")
        return jsonify({"error": f"Failed to write code to file: {str(e)}"}), 500

    command_to_execute = []
    if language == 'python':
        command_to_execute = ["python", full_file_path]
    else:
        # Clean up the created file if language is unsupported
        logging.error(f"Unsupported language: {language} for filename: {filename}")
        if os.path.exists(full_file_path):
            try:
                os.remove(full_file_path)
                logging.info(f"Cleaned up temporary file due to unsupported language: {full_file_path}")
            except OSError as e:
                logging.error(f"Error removing temporary file {full_file_path} after unsupported language error: {str(e)}")
        return jsonify({"error": f"Unsupported language: {language}"}), 400

    logging.info(f"Executing command: {' '.join(command_to_execute)}")
    try:
        result = subprocess.run(
            command_to_execute,
            capture_output=True,
            text=True,
            timeout=30 # Adding a timeout for safety
        )
        status = "success" if result.returncode == 0 else "error"
        logging.info(f"Execution finished for {filename} with return code {result.returncode}. Status: {status}")
        
        return jsonify({
            "status": status,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command_executed": command_to_execute,
            "return_code": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            "status": "error",
            "stdout": "",
            "stderr": "Execution timed out after 30 seconds.",
            "command_executed": command_to_execute,
            "return_code": -1 # Using a distinct return code for timeout
        }), 408 # HTTP 408 Request Timeout
    except Exception as e:
        # Catch any other exception during subprocess.run
        logging.error(f"An unexpected error occurred during execution of {filename}: {str(e)}")
        return jsonify({
            "status": "error",
            "stdout": "",
            "stderr": f"An unexpected error occurred during execution: {str(e)}",
            "command_executed": command_to_execute,
            "return_code": -2 # Using a distinct return code for other execution errors
        }), 500
    finally:
        # Clean up the created file after execution, regardless of outcome
        if os.path.exists(full_file_path):
            try:
                os.remove(full_file_path)
                logging.info(f"Successfully cleaned up temporary file: {full_file_path}")
            except OSError as e:
                # Log this error, but don't let it overwrite the primary response
                logging.error(f"Failed to remove temporary file {full_file_path}: {str(e)}")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
