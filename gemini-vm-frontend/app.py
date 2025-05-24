import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
# At the top of app.py, add to imports:
from gcp_utils import get_vm_status, trigger_vm_creation
import google.generativeai as genai
import json # For parsing Gemini's JSON output string


# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Secret key for session management
app.secret_key = os.urandom(24) 

@app.route('/', methods=['GET'])
def index():
    """Renders the main page with the input form."""
    return render_template('index.html')

@app.route('/process_instruction', methods=['POST'])
def process_instruction_route():
    try:
        data = request.get_json()
        # ... (existing code for getting instruction, VM status check, and VM provisioning trigger) ...
        if not data:
            app.logger.error("No JSON data received.")
            return jsonify({"error": "No JSON data received."}), 400
        user_instruction = data.get('instruction') # Renamed for clarity with Gemini prompt
        if not user_instruction:
            app.logger.error("No instruction provided in JSON data.")
            return jsonify({"error": "No instruction provided in JSON data."}), 400

        app.logger.info(f"Received instruction: {user_instruction}")

        target_vm_name = os.getenv('TARGET_VM_NAME', 'code-runner-vm')
        vm_ip = None
        current_vm_status, vm_ip_or_error_msg = get_vm_status(target_vm_name)
        app.logger.info(f"Initial VM status for '{target_vm_name}': {current_vm_status}, IP/Details: {vm_ip_or_error_msg}")

        if current_vm_status == "RUNNING":
            vm_ip = vm_ip_or_error_msg # This should be the IP address
            app.logger.info(f"VM '{target_vm_name}' is RUNNING with IP: {vm_ip}")
        elif current_vm_status == "ERROR":
            # Error getting VM status, return error to user
            return jsonify({
                "original_instruction": user_instruction,
                "error": f"Error checking VM status: {vm_ip_or_error_msg}",
                "vm_status": current_vm_status
            }), 500
        else: # VM not running (NOT_FOUND, TERMINATED, STOPPED, etc.)
            app.logger.info(f"VM '{target_vm_name}' is not running (status: {current_vm_status}). Attempting to create/start.")
            creation_success, message_or_ip = trigger_vm_creation(target_vm_name)
            if creation_success:
                vm_ip = message_or_ip
                current_vm_status = "RUNNING_AFTER_CREATION" 
                app.logger.info(f"VM '{target_vm_name}' provisioned successfully. IP: {vm_ip}")
            else:
                app.logger.error(f"VM provisioning failed for '{target_vm_name}': {message_or_ip}")
                return jsonify({
                    "original_instruction": user_instruction,
                    "error": f"VM provisioning failed: {message_or_ip}",
                    "vm_status": "PROVISIONING_FAILED"
                }), 500

        if not vm_ip:
            app.logger.error(f"Could not obtain VM IP address for '{target_vm_name}' after status checks and provisioning attempt.")
            return jsonify({
                "original_instruction": user_instruction,
                "error": "Could not obtain VM IP address.",
                "vm_status": current_vm_status
            }), 500

        # --- Start of Step 6: Gemini Interaction --- 
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            app.logger.error("GEMINI_API_KEY not configured.")
            return jsonify({"error": "GEMINI_API_KEY not configured."}), 500

        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-pro') # Or your preferred model

        # Define the system prompt for Gemini.
        system_prompt = (
            "You are an expert coding assistant. Your task is to translate the user's natural language "
            "instruction into a JSON object that specifies code to be run on a Linux VM. "
            "The JSON object must have the following keys: "
            "  - 'filename': A string representing the desired filename for the code (e.g., 'script.py', 'task.sh'). "
            "  - 'code': A string containing the actual code to be written to the file. Escape newlines as \\n. "
            "  - 'language': A string indicating the programming language (e.g., 'python', 'bash'). Default to 'python' if unsure. "
            "If the user asks to run a command directly without creating a file, try to create a simple script for it. "
            "For example, if the user says 'list files in /tmp', you could generate a bash script. "
            "Focus on generating executable code for a single task or script per request. "
            "Ensure the 'code' field contains valid code for the specified 'language'."
            "Output ONLY the JSON object, with no other text before or after it."
        )

        full_prompt = f"{system_prompt}\n\nUser Instruction: {user_instruction}"

        app.logger.info(f"Sending prompt to Gemini for instruction: '{user_instruction}'")
        
        gemini_output_json = None
        gemini_error = None
        gemini_response_text = None # Initialize to avoid reference before assignment in error case
        try:
            response = model.generate_content(full_prompt)
            gemini_response_text = response.text.strip()
            app.logger.info(f"Raw Gemini response: {gemini_response_text}")
            
            if gemini_response_text.startswith('```json'):
                gemini_response_text = gemini_response_text[7:]
            if gemini_response_text.startswith('```'):
                 gemini_response_text = gemini_response_text[3:]
            if gemini_response_text.endswith('```'):
                gemini_response_text = gemini_response_text[:-3]
            gemini_response_text = gemini_response_text.strip()

            gemini_output_json = json.loads(gemini_response_text)
            app.logger.info(f"Parsed Gemini JSON output: {gemini_output_json}")

        except json.JSONDecodeError as je:
            app.logger.error(f"Failed to parse Gemini response as JSON: {je}. Response was: {gemini_response_text}")
            gemini_error = f"Gemini output was not valid JSON: {gemini_response_text}"
        except Exception as e:
            app.logger.error(f"Error during Gemini API call: {e}")
            gemini_error = str(e)
        
        if gemini_error:
             return jsonify({
                "original_instruction": user_instruction,
                "error": f"Error processing with Gemini: {gemini_error}",
                "vm_status": current_vm_status, 
                "vm_ip": vm_ip 
            }), 500
        
        if not gemini_output_json or not all(k in gemini_output_json for k in ['filename', 'code', 'language']):
            app.logger.error(f"Gemini output missing required fields. Output: {gemini_output_json}")
            return jsonify({
                "original_instruction": user_instruction,
                "error": "Gemini output did not contain all required fields (filename, code, language).",
                "vm_status": current_vm_status,
                "vm_ip": vm_ip,
                "gemini_raw_output": gemini_response_text if 'gemini_response_text' in locals() else 'N/A'
            }), 500
        # --- End of Step 6 --- 

        # TODO: Step 7 - Implement Sompaak Runner Interaction (using vm_ip and gemini_output_json)

        return jsonify({
            "original_instruction": user_instruction,
            "message": "Gemini processing complete. Runner interaction pending.",
            "vm_status": current_vm_status, 
            "vm_ip": vm_ip, 
            "gemini_output": gemini_output_json,
            "runner_output": "PENDING_IMPLEMENTATION"
        })

    except Exception as e:
        app.logger.error(f"Critical error in /process_instruction: {e}", exc_info=True)
        return jsonify({"error": f"An unexpected critical error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.logger.info("Starting Flask app on port 5001")
    app.run(debug=True, host='0.0.0.0', port=5001)
